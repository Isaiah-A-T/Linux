"""The Lumen Store: Flathub and the Snap Store in one catalogue.

Search goes to both stores at once. An app found in both is shown once, and
installs from Flathub (no extra daemon, sandboxed by default) unless the user
picks Snap on the app page.
"""

import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from . import jobs, mock
from .util import ApiError, mock_enabled, run

FLATHUB = "https://flathub.org/api/v2"
SNAP = "https://api.snapcraft.io/v2"
_SNAP_HEADERS = {"Snap-Device-Series": "16", "User-Agent": "lumen-store/0.1"}
_SNAP_FIELDS = "title,summary,description,media,publisher,version,store-url"

_cache = {}


def _get(url, headers=None, data=None, ttl=900):
    key = (url, data)
    hit = _cache.get(key)
    if hit and hit[0] > time.time() - ttl:
        return hit[1]
    req = urllib.request.Request(url, headers={"User-Agent": "lumen-store/0.1", **(headers or {})},
                                 data=data.encode() if data else None)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        value = json.load(resp)
    _cache[key] = (time.time(), value)
    return value


def norm(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def _flathub_card(hit):
    return {
        "source": "flatpak",
        "id": hit.get("app_id") or hit.get("id"),
        "title": hit.get("name", ""),
        "summary": hit.get("summary", ""),
        "icon": hit.get("icon"),
        "developer": hit.get("developer_name", ""),
    }


def _snap_card(result):
    snap = result.get("snap", {})
    icon = next((m["url"] for m in snap.get("media", []) if m.get("type") == "icon"), None)
    return {
        "source": "snap",
        "id": result.get("name"),
        "title": snap.get("title") or result.get("name"),
        "summary": snap.get("summary", ""),
        "icon": icon,
        "developer": (snap.get("publisher") or {}).get("display-name", ""),
    }


def merge(flatpaks, snaps):
    """Interleave both result lists; one card per app, Flatpak preferred."""
    out, by_key = [], {}
    for card in flatpaks + snaps:
        key = norm(card["title"])
        if key in by_key:
            by_key[key].setdefault("also", []).append({"source": card["source"], "id": card["id"]})
            continue
        card = dict(card)
        by_key[key] = card
        out.append(card)
    # Keep relevance order but don't let one store bury the other.
    flat = [c for c in out if c["source"] == "flatpak"]
    snap = [c for c in out if c["source"] == "snap"]
    merged = []
    while flat or snap:
        merged.extend(flat[:2])
        merged.extend(snap[:1])
        flat, snap = flat[2:], snap[1:]
    return merged


def _parallel(*funcs):
    results = [[] for _ in funcs]

    def call(i, f):
        try:
            results[i] = f()
        except (OSError, ValueError):
            results[i] = []

    threads = [threading.Thread(target=call, args=(i, f)) for i, f in enumerate(funcs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    return results


def _mock_cards(query=""):
    q = query.lower()
    cards = []
    for source, app_id, title, summary, dev in mock.STORE_APPS:
        if q and q not in title.lower() and q not in summary.lower():
            continue
        cards.append({"source": source, "id": app_id, "title": title, "summary": summary,
                      "developer": dev, "icon": f"/api/mock-art/store:{title}.svg?shape=icon"})
    return cards


def featured():
    if mock_enabled():
        return {"sections": [
            {"title": "Popular", "apps": _mock_cards()[:8]},
            {"title": "For gamers", "apps": [c for c in _mock_cards() if c["title"] in
                                             ("Discord", "Lutris", "OBS Studio", "Proton GE", "RetroArch", "Prism Launcher")]},
            {"title": "Watch and listen", "apps": [c for c in _mock_cards() if c["title"] in
                                                   ("Spotify", "VLC", "Kodi", "Plex")]},
        ]}
    flat, snap = _parallel(
        lambda: [_flathub_card(h) for h in _get(f"{FLATHUB}/collection/popular?per_page=24").get("hits", [])],
        lambda: [_snap_card(r) for r in _get(f"{SNAP}/snaps/find?category=featured&fields={_SNAP_FIELDS}",
                                             _SNAP_HEADERS).get("results", [])],
    )
    games, = _parallel(
        lambda: [_flathub_card(h) for h in _get(f"{FLATHUB}/collection/category/Game?per_page=12").get("hits", [])],
    )
    return {"sections": [
        {"title": "Popular", "apps": merge(flat[:12], snap[:6])},
        {"title": "For gamers", "apps": games},
    ]}


def search(query):
    query = (query or "").strip()
    if not query:
        return {"apps": []}
    if mock_enabled():
        return {"apps": _mock_cards(query)}
    flat, snap = _parallel(
        lambda: [_flathub_card(h) for h in
                 _get(f"{FLATHUB}/search", data=json.dumps({"query": query}), ttl=300).get("hits", [])[:30]],
        lambda: [_snap_card(r) for r in _get(
            f"{SNAP}/snaps/find?q={urllib.parse.quote(query)}&fields={_SNAP_FIELDS}",
            _SNAP_HEADERS, ttl=300).get("results", [])[:20]],
    )
    return {"apps": merge(flat, snap)}


def strip_html(text):
    """Flathub descriptions are AppStream HTML; the UI shows plain paragraphs."""
    text = re.sub(r"</(p|li)>", "\n", text or "")
    text = re.sub(r"<li>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(text)).strip()


def details(source, app_id):
    if mock_enabled():
        card = next((c for c in _mock_cards() if c["id"] == app_id), None)
        if not card:
            raise ApiError("App not found.", 404)
        return {**card, "description": f"{card['summary']}.\n\nThis is sample text shown while "
                "Lumen runs with mock data. On a real system the description, screenshots "
                "and developer come straight from Flathub or the Snap Store.",
                "screenshots": [f"/api/mock-art/shot:{card['title']}:{n}.svg?shape=hero" for n in (1, 2)],
                "installed": app_id in mock.state.setdefault("store_installed", set())}
    if source == "flatpak":
        data = _get(f"{FLATHUB}/appstream/{urllib.parse.quote(app_id)}")
        shots = []
        for s in data.get("screenshots", [])[:6]:
            sizes = s.get("sizes", {})
            if sizes:
                shots.append(sizes[max(sizes, key=lambda k: int(k.split("x")[0]))])
        return {
            "source": source, "id": app_id, "title": data.get("name", app_id),
            "summary": data.get("summary", ""), "description": strip_html(data.get("description")),
            "icon": data.get("icon"), "developer": data.get("developer_name", ""),
            "screenshots": shots, "installed": app_id in installed_flatpaks(),
        }
    if source == "snap":
        data = _get(f"{SNAP}/snaps/info/{urllib.parse.quote(app_id)}?fields={_SNAP_FIELDS}", _SNAP_HEADERS)
        snap = data.get("snap", {})
        card = _snap_card(data)
        return {
            **card, "description": snap.get("description", ""),
            "screenshots": [m["url"] for m in snap.get("media", []) if m.get("type") == "screenshot"][:6],
            "installed": app_id in installed_snaps(),
        }
    raise ApiError("Unknown store.")


def installed_flatpaks():
    return set(run(["flatpak", "list", "--app", "--columns=application"]).split())


def installed_snaps():
    lines = run(["snap", "list"]).splitlines()[1:]
    return {line.split()[0] for line in lines if line.strip()}


_VALID_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def install(source, app_id):
    if not _VALID_ID.match(app_id or ""):
        raise ApiError("Invalid app id.")
    if mock_enabled():
        mock.state.setdefault("store_installed", set()).add(app_id)
        return jobs.fake(f"Installing {app_id}", item_id=f"{source}:{app_id}", seconds=4)
    if source == "flatpak":
        run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
             "https://dl.flathub.org/repo/flathub.flatpakrepo"], timeout=60)
        cmd = ["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", app_id]
    elif source == "snap":
        cmd = ["snap", "install", app_id]
    else:
        raise ApiError("Unknown store.")
    return jobs.start(f"Installing {app_id}", cmd, item_id=f"{source}:{app_id}")


def remove(source, app_id):
    if not _VALID_ID.match(app_id or ""):
        raise ApiError("Invalid app id.")
    if mock_enabled():
        mock.state.setdefault("store_installed", set()).discard(app_id)
        return {"ok": True}
    if source == "flatpak":
        cmd = ["flatpak", "uninstall", "--user", "--noninteractive", "-y", app_id]
    elif source == "snap":
        cmd = ["snap", "remove", app_id]
    else:
        raise ApiError("Unknown store.")
    return jobs.start(f"Removing {app_id}", cmd, item_id=f"{source}:{app_id}")
