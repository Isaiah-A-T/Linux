"""Cover and background art for games.

Every game gets Steam's artwork when Steam sells it, because Steam has the
same set of images (portrait cover, wide hero) for almost every PC game.
Steam games use their own app id. Epic, GOG and desktop games are matched
to a Steam app by title in the background; the store's own images are the
fallback, and a generated cover is the last resort.

Images are fetched once through /api/art and kept in ~/.cache/lumen/art, so
the shell works offline after the first look.
"""

import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .util import data_dir, load_json, save_json

STEAM_CDNS = (
    "https://shared.steamstatic.com/store_item_assets/steam/apps",
    "https://cdn.cloudflare.steamstatic.com/steam/apps",
)
SEARCH = "https://store.steampowered.com/api/storesearch/?cc=us&l=en&term="
DETAILS = "https://store.steampowered.com/api/appdetails?filters=basic&appids="

# Hosts /api/art may download from: Steam, Epic and GOG image CDNs.
ALLOWED_HOSTS = ("steamstatic.com", "steampowered.com", "epicgames.com", "unrealengine.com",
                 "gog-statics.com", "gog.com")
MAX_BYTES = 15 * 1024 * 1024
MISS_RETRY = 24 * 3600
LOOKUP_RETRY = 7 * 24 * 3600

_index_lock = threading.Lock()
_pending = set()
_on_found = []


# --- Matching store titles to Steam ------------------------------------------

_EDITION = re.compile(
    r"\b(game of the year|goty|complete|definitive|deluxe|ultimate|gold|enhanced|remastered|"
    r"director'?s cut|anniversary|standard)( edition)?\b|\bedition\b")


def normalize(title):
    t = title.lower().replace("&", "and")
    t = re.sub(r"[™®©]", "", t)
    t = _EDITION.sub(" ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"^the ", "", t.strip())


def _subtitle_of(name, want):
    """True when a Steam name is the title plus a subtitle ("Disco Elysium - The Final Cut")."""
    plain = re.sub(r"\s+", " ", re.sub(r"[™®©]", "", name.lower())).strip()
    return any(plain.startswith(want + sep) for sep in (": ", " - ", " – "))


def best_match(title, results):
    """The Steam app id whose name matches the title, or None."""
    want = normalize(title)
    if not want:
        return None
    names = [(str(r.get("id")), normalize(r.get("name", "")), r.get("name", "")) for r in results if r.get("id")]
    for appid, name, _ in names:
        if name == want:
            return appid
    raw = re.sub(r"\s+", " ", re.sub(r"[™®©]", "", title.lower())).strip()
    for appid, _, original in names:
        # "The Witcher 3" is "The Witcher 3: Wild Hunt", but "Portal" isn't "Portal 2".
        if _subtitle_of(original, raw):
            return appid
    return None


def _index_path():
    return data_dir() / "art-index.json"


def _fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Lumen/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(2 * 1024 * 1024))


def _lookup(title):
    """Ask the Steam store for a title. Returns (appid or None, background or None)."""
    results = _fetch_json(SEARCH + urllib.parse.quote(title)).get("items", [])
    appid = best_match(title, results)
    if not appid:
        return None, None
    try:
        data = _fetch_json(DETAILS + appid).get(appid, {}).get("data", {})
        return appid, data.get("background_raw")
    except (OSError, ValueError):
        return appid, None


def _resolve_all(titles):
    for title in titles:
        try:
            appid, background = _lookup(title)
        except (OSError, ValueError):
            continue  # offline; try again next time the library loads
        with _index_lock:
            index = load_json(_index_path(), {})
            index[normalize(title)] = {"appid": appid, "background": background, "time": time.time()}
            save_json(_index_path(), index)
    with _index_lock:
        _pending.difference_update(titles)
    for fn in _on_found:
        fn()


def on_found(fn):
    """Call fn after a batch of background lookups finishes."""
    _on_found.append(fn)


def steam_match(title, index):
    entry = index.get(normalize(title))
    if entry and (entry["appid"] or entry["time"] > time.time() - LOOKUP_RETRY):
        return entry, False
    return None, True


# --- URLs ----------------------------------------------------------------------

def art_url(candidates, fallback=None):
    """A /api/art URL that serves the first candidate that downloads."""
    params = [("u", c) for c in candidates if c and c.startswith("https://")]
    if fallback:
        params.append(("f", fallback))
    if not params:
        return None
    return "/api/art?" + urllib.parse.urlencode(params)


def steam_candidates(appid, background=None):
    cover = [f"{cdn}/{appid}/{name}" for name in ("library_600x900_2x.jpg", "library_600x900.jpg")
             for cdn in STEAM_CDNS]
    hero = [f"{cdn}/{appid}/library_hero.jpg" for cdn in STEAM_CDNS]
    if background:
        hero.append(background)
    hero.append(f"{STEAM_CDNS[1]}/{appid}/header.jpg")
    return cover, hero


def placeholder(item, shape):
    return f"/api/placeholder-art?{urllib.parse.urlencode({'title': item['title'], 'key': item['id'], 'shape': shape})}"


def enrich(items, lookups=True):
    """Fill in cover and hero art for every game. Apps keep their icons."""
    with _index_lock:
        index = load_json(_index_path(), {})
    missing = []
    for item in items:
        if item.get("kind") != "game":
            continue
        own = item.get("art") or {}
        source, _, ident = item["id"].partition(":")
        if own.get("cover", "").startswith("/api/mock-art/"):
            own = {}  # mock mode: generated art is only the last resort
        cover, hero = [], []
        if source == "steam":
            cover, hero = steam_candidates(ident)
        else:
            entry, need = steam_match(item["title"], index)
            if need:
                missing.append(item["title"])
            elif entry["appid"]:
                cover, hero = steam_candidates(entry["appid"], entry.get("background"))
        cover += [own.get("cover")]
        hero += [own.get("hero"), own.get("cover")]
        item["art"] = {
            **own,
            "cover": art_url(cover, placeholder(item, "cover")),
            "hero": art_url(hero, placeholder(item, "hero")),
        }
    if lookups and missing:
        with _index_lock:
            fresh = [t for t in dict.fromkeys(missing) if t not in _pending]
            _pending.update(fresh)
        if fresh:
            threading.Thread(target=_resolve_all, args=(fresh,), daemon=True).start()
    return items


# --- Image cache -------------------------------------------------------------

def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = Path(base) / "lumen" / "art"
    path.mkdir(parents=True, exist_ok=True)
    return path


def allowed(url):
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def fetch(url):
    """Return (bytes, content type) for an image, from the cache or the web, or None."""
    if not allowed(url):
        return None
    key = hashlib.sha1(url.encode()).hexdigest()
    path, meta, miss = (cache_dir() / key, cache_dir() / f"{key}.type", cache_dir() / f"{key}.miss")
    if path.is_file():
        return path.read_bytes(), (meta.read_text() if meta.is_file() else "image/jpeg")
    if miss.is_file() and miss.stat().st_mtime > time.time() - MISS_RETRY:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Lumen/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            ctype = resp.headers.get_content_type()
            data = resp.read(MAX_BYTES + 1)
        if not ctype.startswith("image/") or len(data) > MAX_BYTES:
            raise ValueError("not an image")
    except (OSError, ValueError):
        miss.touch()
        return None
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    meta.write_text(ctype)
    return data, ctype


def first_image(candidates):
    for url in candidates:
        got = fetch(url)
        if got:
            return got
    return None
