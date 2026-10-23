"""Steam: Steam keeps its own client, login and Proton. We list and launch.

Lumen turns on Steam Play for every title, so Windows-only games install and
run with Proton without a trip into Steam's settings, and lets you pick a
different Proton per game from the game's page.
"""

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ..util import ApiError, data_dir, have, load_json, run, save_json, session_env
from . import vdf
from .base import Launcher

CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"

# Runtime and Proton entries Steam installs as "apps"; they are not games.
_TOOL_IDS = {"228980", "1070560", "1391110", "1628350", "1493710", "2180100", "2348590", "1826330"}


def steam_root():
    for p in ("~/.local/share/Steam", "~/.steam/steam", "~/.var/app/com.valvesoftware.Steam/data/Steam"):
        path = Path(os.path.expanduser(p))
        if (path / "steamapps").is_dir() or (path / "config").is_dir():
            return path
    return None


# Proton builds Valve ships. Steam downloads the one a game is set to on its
# own, so these are always offered. Custom builds (GE-Proton, which umu also
# uses for Epic and GOG) come from compatibilitytools.d.
VALVE_PROTONS = [
    ("proton_experimental", "Proton Experimental"),
    ("proton_10", "Proton 10.0"),
    ("proton_9", "Proton 9.0"),
    ("proton_8", "Proton 8.0"),
    ("proton_hotfix", "Proton Hotfix"),
]
DEFAULT_PROTON = "proton_experimental"
_SYSTEM_TOOLS = Path("/usr/share/steam/compatibilitytools.d")

# Steam Deck compatibility categories from Steam's store.
_DECK = {1: "unsupported", 2: "playable", 3: "verified"}


def is_tool(appid, name):
    return appid in _TOOL_IDS or name.startswith(("Proton", "Steam Linux Runtime", "Steamworks"))


def art(appid):
    return {
        "cover": f"{CDN}/{appid}/library_600x900.jpg",
        "hero": f"{CDN}/{appid}/library_hero.jpg",
        "icon": f"{CDN}/{appid}/header.jpg",
    }


def library_folders(root):
    lib = root / "steamapps" / "libraryfolders.vdf"
    folders = [root]
    if lib.exists():
        data = vdf.load(lib).get("libraryfolders", {})
        for entry in data.values():
            if isinstance(entry, dict) and entry.get("path"):
                p = Path(entry["path"])
                if p not in folders:
                    folders.append(p)
    return folders


def installed_games(root):
    games = {}
    for folder in library_folders(root):
        for acf in (folder / "steamapps").glob("appmanifest_*.acf"):
            try:
                st = vdf.load(acf).get("AppState", {})
            except OSError:
                continue
            appid, name = st.get("appid", ""), st.get("name", "")
            if not appid or is_tool(appid, name):
                continue
            total = int(st.get("BytesToDownload") or 0)
            done = int(st.get("BytesDownloaded") or 0)
            flags = int(st.get("StateFlags") or 0)
            games[appid] = {
                "title": name,
                "installed": flags & 4 == 4,  # StateFlags bit 2 = fully installed
                "last_played": int(st.get("LastPlayed") or 0) or None,
                "size": int(st.get("SizeOnDisk") or 0),
                "progress": round(100 * done / total, 1) if total and done < total else None,
            }
    return games


def logged_in_user(root):
    users = root / "config" / "loginusers.vdf"
    if not users.exists():
        return None
    data = vdf.load(users).get("users", {})
    best = None
    for steamid, info in data.items():
        if not isinstance(info, dict):
            continue
        if best is None or info.get("MostRecent") == "1":
            best = (steamid, info.get("PersonaName") or info.get("AccountName"))
    return best


def running():
    return bool(run(["pgrep", "-x", "steam"]).strip())


def _default_root():
    # Where Arch's steam bootstrapper unpacks the client on first start.
    return Path(os.path.expanduser("~/.local/share/Steam"))


def _child(d, name):
    """d[name], matching the key case-insensitively (Steam isn't consistent)."""
    for key, value in d.items():
        if key.lower() == name.lower() and isinstance(value, dict):
            return value
    d[name] = {}
    return d[name]


def _mapping(cfg):
    node = cfg
    for name in ("InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"):
        node = _child(node, name)
    return node


def _read_config(root):
    path = root / "config" / "config.vdf"
    try:
        return vdf.load(path)
    except OSError:
        return {}


def _write_config(root, cfg):
    path = root / "config" / "config.vdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name("config.vdf.lumen-bak")
    if path.exists() and not backup.exists():
        backup.write_bytes(path.read_bytes())
    tmp = path.with_suffix(".vdf.tmp")
    tmp.write_text(vdf.dumps(cfg))
    tmp.replace(path)


def enable_steam_play(root=None):
    """Turn on "Enable Steam Play for all other titles" with Proton Experimental.

    Steam rewrites config.vdf on exit, so this only writes while Steam is
    closed. It leaves the setting alone if the user changed it in Steam.
    """
    root = root or steam_root() or _default_root()
    if running():
        return False
    cfg = _read_config(root)
    mapping = _mapping(cfg)
    if "0" in mapping:
        return False
    mapping["0"] = {"name": DEFAULT_PROTON, "config": "", "priority": "75"}
    _write_config(root, cfg)
    return True


def compat_tools(root):
    tools = [{"id": tid, "name": name} for tid, name in VALVE_PROTONS]
    seen = {t["id"] for t in tools}
    for base in (root / "compatibilitytools.d", _SYSTEM_TOOLS):
        for manifest in sorted(base.glob("*/compatibilitytool.vdf")):
            try:
                entries = vdf.load(manifest).get("compatibilitytools", {}).get("compat_tools", {})
            except OSError:
                continue
            for tid, info in entries.items():
                if tid not in seen and isinstance(info, dict):
                    seen.add(tid)
                    tools.append({"id": tid, "name": info.get("display_name") or tid})
    return tools


def _wait_for_exit(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if not running():
            return True
        time.sleep(0.5)
    return False


def ratings(appid):
    """ProtonDB tier and Steam Deck status, cached for a week."""
    path = data_dir() / "steam-ratings.json"
    cache = load_json(path, {})
    hit = cache.get(appid)
    # Offline misses are retried after an hour instead of a week.
    ttl = 7 * 86400 if hit and any(hit["ratings"].values()) else 3600
    if hit and hit.get("time", 0) > time.time() - ttl:
        return hit["ratings"]
    out = {"protondb": None, "deck": None}
    try:
        with urllib.request.urlopen(
            f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json", timeout=8
        ) as resp:
            out["protondb"] = json.load(resp).get("tier")
    except (OSError, ValueError):
        pass
    try:
        with urllib.request.urlopen(
            "https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?"
            + urllib.parse.urlencode({"nAppID": appid}), timeout=8
        ) as resp:
            category = (json.load(resp).get("results") or {}).get("resolved_category")
            out["deck"] = _DECK.get(category)
    except (OSError, ValueError, AttributeError):
        pass
    cache[appid] = {"time": time.time(), "ratings": out}
    save_json(path, cache)
    return out


class Steam(Launcher):
    id = "steam"
    name = "Steam"
    login = {
        "type": "steam",
        "help": "Steam opens its own sign-in screen. Sign in there, then come back here.",
        "optional_api_key": "https://steamcommunity.com/dev/apikey",
    }

    def _cfg_path(self):
        return data_dir() / "steam.json"

    def available(self):
        return have("steam")

    def status(self):
        root = steam_root()
        user = logged_in_user(root) if root else None
        return {"connected": bool(user), "user": user[1] if user else None}

    def connect(self, payload):
        # Optional Web API key lets us list games that aren't installed yet.
        if payload.get("api_key"):
            cfg = load_json(self._cfg_path(), {})
            cfg["api_key"] = payload["api_key"].strip()
            save_json(self._cfg_path(), cfg)
        if not self.status()["connected"]:
            if not self.available():
                raise ApiError("Steam isn't installed.")
            enable_steam_play()
            subprocess.Popen(["steam", "-silent" if payload.get("api_key") else "steam://open/main"],
                             env=session_env(), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.describe()

    def disconnect(self):
        cfg_path = self._cfg_path()
        if cfg_path.exists():
            cfg_path.unlink()
        if have("steam"):
            subprocess.Popen(["steam", "-shutdown"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.describe()

    def _owned(self):
        """Owned games from the Steam Web API, cached for an hour."""
        cfg = load_json(self._cfg_path(), {})
        root = steam_root()
        user = logged_in_user(root) if root else None
        if not cfg.get("api_key") or not user:
            return {}
        cache = cfg.get("owned_cache", {})
        if cache.get("time", 0) > time.time() - 3600:
            return cache["games"]
        query = urllib.parse.urlencode({
            "key": cfg["api_key"], "steamid": user[0], "include_appinfo": 1, "format": "json",
        })
        try:
            with urllib.request.urlopen(
                f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?{query}", timeout=15
            ) as resp:
                data = json.load(resp)
        except (OSError, ValueError):
            return cache.get("games", {})
        games = {
            str(g["appid"]): {"title": g.get("name", str(g["appid"])),
                              "last_played": g.get("rtime_last_played") or None}
            for g in data.get("response", {}).get("games", [])
        }
        cfg["owned_cache"] = {"time": time.time(), "games": games}
        save_json(self._cfg_path(), cfg)
        return games

    def games(self):
        root = steam_root()
        if not root:
            return []
        installed = installed_games(root)
        merged = {appid: {**g, "installed": False} for appid, g in self._owned().items()}
        for appid, g in installed.items():
            merged[appid] = {**merged.get(appid, {}), **g}
        return [
            {"id": f"steam:{appid}", "title": g["title"], "source": "steam", "kind": "game",
             "installed": g.get("installed", False), "last_played": g.get("last_played"),
             "progress": g.get("progress"), "art": art(appid)}
            for appid, g in merged.items()
        ]

    def _open(self, url, quiet=True):
        if not have("steam"):
            raise ApiError("Steam isn't installed.")
        enable_steam_play()
        # -silent keeps Steam's own window from covering Lumen; the game (or
        # Steam's install dialog) still comes to the front.
        args = ["steam", "-silent", url] if quiet else ["steam", url]
        subprocess.Popen(args, env=session_env(), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def compat(self, game_id):
        """Which Proton a game runs with, the choices, and how well it runs."""
        root = steam_root() or _default_root()
        mapping = _mapping(_read_config(root))
        entry, default = mapping.get(game_id), mapping.get("0")
        tools = compat_tools(root)
        names = {t["id"]: t["name"] for t in tools}
        default_id = default.get("name") if isinstance(default, dict) else DEFAULT_PROTON
        return {
            "tool": entry.get("name", "") if isinstance(entry, dict) else "",
            "default": names.get(default_id, default_id),
            "tools": tools,
            "steam_running": running(),
            **ratings(game_id),
        }

    def set_compat(self, game_id, tool):
        """Force a Proton for one game, or "" to let Steam decide.

        Steam keeps this setting in config.vdf and overwrites the file when it
        exits, so Steam is closed first. It starts again with the next game.
        """
        root = steam_root() or _default_root()
        if tool and tool not in {t["id"] for t in compat_tools(root)}:
            raise ApiError("That version of Proton isn't available.")
        if running():
            run(["steam", "-shutdown"])
            if not _wait_for_exit():
                raise ApiError("Steam didn't close. Try again in a moment.")
        cfg = _read_config(root)
        mapping = _mapping(cfg)
        if tool:
            mapping[game_id] = {"name": tool, "config": "", "priority": "250"}
        else:
            mapping.pop(game_id, None)
        if "0" not in mapping:
            mapping["0"] = {"name": DEFAULT_PROTON, "config": "", "priority": "75"}
        _write_config(root, cfg)
        return self.compat(game_id)

    def install(self, game_id):
        # Steam downloads with its own Proton; progress shows up in the
        # appmanifest, which games() reports.
        self._open(f"steam://install/{game_id}", quiet=False)
        return None

    def uninstall(self, game_id):
        self._open(f"steam://uninstall/{game_id}", quiet=False)

    def launch(self, game_id):
        self._open(f"steam://rungameid/{game_id}")
