"""One library across Steam, Epic, GOG and regular desktop apps."""

import os
import threading
import time

from . import apps, art, jobs, mock, recents
from .launchers import LAUNCHERS
from .util import ApiError, mock_enabled

_cache = {"time": 0, "items": []}
_lock = threading.Lock()
_TTL = 20


def items(refresh=False):
    if mock_enabled():
        return _mock_items()
    with _lock:
        if not refresh and _cache["time"] > time.time() - _TTL:
            return _cache["items"]
        out = []
        for launcher in LAUNCHERS.values():
            try:
                out.extend(launcher.games())
            except Exception:  # one broken launcher must not empty the library
                continue
        out.extend(apps.list_apps())
        art.enrich(out)
        _cache.update(time=time.time(), items=out)
        return out


def _forget():
    _cache["time"] = 0


art.on_found(_forget)


def _mock_items():
    out = art.enrich(mock.library())
    installed = mock.state.setdefault("installed_extra", set())
    for item in out:
        if item["id"] in installed:
            item["installed"] = True
    return out


def public(item):
    return {k: v for k, v in item.items() if not k.startswith("_")}


def get(item_id):
    for item in items():
        if item["id"] == item_id:
            return item
    raise ApiError("That game or app isn't in your library.", 404)


def overview():
    all_items = items()
    counts = {}
    for item in all_items:
        counts[item["source"]] = counts.get(item["source"], 0) + 1
    return {
        "items": [public(i) for i in sorted(all_items, key=lambda i: i["title"].lower())],
        "counts": counts,
    }


def home():
    return [public(i) for i in recents.home_items(items())]


def _split(item_id):
    source, _, ident = item_id.partition(":")
    return source, ident


def launch(item_id):
    item = get(item_id)
    if not item.get("installed"):
        raise ApiError(f"{item['title']} isn't installed yet.")
    recents.touch(item)
    if mock_enabled():
        return {"ok": True}
    source, ident = _split(item_id)
    if source == "app":
        apps.launch(item)
    else:
        LAUNCHERS[source].launch(ident)
    return {"ok": True}


def install(item_id):
    source, ident = _split(item_id)
    if mock_enabled():
        mock.state.setdefault("installed_extra", set()).add(item_id)
        return jobs.fake(f"Installing {get(item_id)['title']}", item_id=item_id)
    if source not in LAUNCHERS:
        raise ApiError("Apps are installed from the Store.")
    job = LAUNCHERS[source].install(ident)
    _cache["time"] = 0
    return job or {"ok": True}


def uninstall(item_id):
    source, ident = _split(item_id)
    recents.forget(item_id)
    if mock_enabled():
        mock.state.setdefault("installed_extra", set()).discard(item_id)
        return {"ok": True}
    if source not in LAUNCHERS:
        raise ApiError("Remove apps from the Store.")
    LAUNCHERS[source].uninstall(ident)
    _cache["time"] = 0
    return {"ok": True}


def _steam_game(item_id):
    source, ident = _split(item_id)
    if source != "steam" or not ident.isdigit():
        raise ApiError("Proton settings are only for Steam games.")
    return ident


def compat(item_id):
    appid = _steam_game(item_id)
    if mock_enabled():
        return mock.steam_compat(appid)
    return LAUNCHERS["steam"].compat(appid)


def set_compat(item_id, tool):
    appid = _steam_game(item_id)
    if mock_enabled():
        return mock.set_steam_compat(appid, tool)
    return LAUNCHERS["steam"].set_compat(appid, tool or "")


def accounts():
    if mock_enabled():
        return [{"id": k, "name": LAUNCHERS[k].name, "available": True, "login": LAUNCHERS[k].login,
                 **v} for k, v in mock.accounts.items()]
    return [l.describe() for l in LAUNCHERS.values()]


def connect(launcher_id, payload):
    if launcher_id not in LAUNCHERS:
        raise ApiError("Unknown launcher.")
    if mock_enabled():
        mock.accounts[launcher_id] = {"connected": True, "user": "Player"}
        return accounts()
    LAUNCHERS[launcher_id].connect(payload)
    _cache["time"] = 0
    return accounts()


def disconnect(launcher_id):
    if launcher_id not in LAUNCHERS:
        raise ApiError("Unknown launcher.")
    if mock_enabled():
        mock.accounts[launcher_id] = {"connected": False, "user": None}
        return accounts()
    LAUNCHERS[launcher_id].disconnect()
    _cache["time"] = 0
    return accounts()


def open_url(url):
    """Open a sign-in page in its own fullscreen Chromium window."""
    if not url.startswith("https://"):
        raise ApiError("Only https pages can be opened.")
    if not mock_enabled():
        import subprocess
        state = os.path.expanduser("~/.local/state/lumen/chromium-web")
        subprocess.Popen(["chromium", f"--user-data-dir={state}", "--start-fullscreen", f"--app={url}"],
                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}
