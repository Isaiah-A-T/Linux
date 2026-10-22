"""Steam: Steam keeps its own client, login and Proton. We list and launch."""

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ..util import ApiError, data_dir, have, load_json, save_json
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
            subprocess.Popen(["steam", "-silent" if payload.get("api_key") else "steam://open/main"],
                             start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def _open(self, url):
        if not have("steam"):
            raise ApiError("Steam isn't installed.")
        subprocess.Popen(["steam", url], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def install(self, game_id):
        # Steam downloads with its own Proton; progress shows up in the
        # appmanifest, which games() reports.
        self._open(f"steam://install/{game_id}")
        return None

    def uninstall(self, game_id):
        self._open(f"steam://uninstall/{game_id}")

    def launch(self, game_id):
        self._open(f"steam://rungameid/{game_id}")
