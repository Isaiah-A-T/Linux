"""Cloud saves: each store's own cloud, synced around every play session.

Steam Cloud is handled by the Steam client. Epic (legendary sync-saves) and
GOG (gogdl save-sync) don't sync by themselves, so Lumen pulls the cloud copy
before a game starts and pushes the new saves once the game and everything
else in its Wine prefix has exited.
"""

import getpass
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from . import jobs
from .util import data_dir, have, load_json, mock_enabled, run, save_json

GOG_VARS = {
    "<?DOCUMENTS?>": "Documents",
    "<?SAVED_GAMES?>": "Saved Games",
    "<?APPLICATION_DATA_ROAMING?>": "AppData/Roaming",
    "<?APPLICATION_DATA_LOCAL?>": "AppData/Local",
    "<?APPLICATION_DATA_LOCAL_LOW?>": "AppData/LocalLow",
}


def _path():
    return data_dir() / "saves.json"


def _load():
    return load_json(_path(), {})


def enabled():
    return _load().get("enabled", True)


def set_enabled(value):
    s = _load()
    s["enabled"] = bool(value)
    save_json(_path(), s)
    return status()


def _mark(item_id, ok):
    s = _load()
    s.setdefault("games", {})[item_id] = {"time": time.time(), "ok": ok}
    s["last_sync"] = time.time()
    save_json(_path(), s)


def last_sync(item_id):
    return _load().get("games", {}).get(item_id)


def status():
    from .launchers import LAUNCHERS
    s = _load()
    if mock_enabled():
        connected = {"steam": True, "epic": True, "gog": False}
    else:
        connected = {}
        for key in ("steam", "epic", "gog"):
            try:
                connected[key] = LAUNCHERS[key].available() and LAUNCHERS[key].status()["connected"]
            except Exception:
                connected[key] = False
    return {
        "enabled": s.get("enabled", True),
        "last_sync": s.get("last_sync"),
        "stores": [
            {"id": "steam", "name": "Steam", "connected": connected["steam"],
             "how": "Steam Cloud, synced by Steam"},
            {"id": "epic", "name": "Epic Games", "connected": connected["epic"],
             "how": "Epic cloud saves, synced before and after you play"},
            {"id": "gog", "name": "GOG", "connected": connected["gog"],
             "how": "GOG Galaxy cloud saves, synced before and after you play"},
        ],
    }


# --- Play sessions -----------------------------------------------------------


def play(item_id, title, prefix, start, sync):
    """Run a game with its saves synced on both sides.

    start() launches the game and returns its Popen. sync(direction) syncs
    with "down" or "up" and returns True on success. Returns right away; the
    sync and the wait happen on a thread.
    """
    if not enabled() or mock_enabled():
        start()
        return

    def session():
        _step(item_id, title, sync, "down")
        proc = start()
        proc.wait()
        wait_prefix_idle(prefix)
        _step(item_id, title, sync, "up")

    threading.Thread(target=session, daemon=True, name=f"saves:{item_id}").start()


def _step(item_id, title, sync, direction):
    job = jobs.begin(f"Cloud saves · {title}", f"saves:{item_id}",
                     "Getting your saves" if direction == "down" else "Uploading your saves")
    try:
        ok = sync(direction)
    except Exception as exc:  # never keep a game from starting over a sync
        ok = False
        job["detail"] = str(exc)
    _mark(item_id, ok)
    jobs.end(job, ok, "Up to date" if ok else "Couldn't sync, your saves on this console are kept")
    return ok


def wait_prefix_idle(prefix, poll=5.0):
    """Wait until no process is running in this Wine prefix.

    The launcher can exit before the game does (legendary hands off to
    umu-run, Proton starts the game in the background), so watch the prefix.
    """
    needle = f"WINEPREFIX={prefix}".encode()
    while True:
        busy = False
        for env in Path("/proc").glob("[0-9]*/environ"):
            try:
                if needle in env.read_bytes().split(b"\0"):
                    busy = True
                    break
            except OSError:
                continue
        if not busy:
            return
        time.sleep(poll)


def sync_all():
    """Settings › Sync now: two-way sync for every installed Epic and GOG game."""
    if mock_enabled():
        s = _load()
        s["last_sync"] = time.time()
        save_json(_path(), s)
        return jobs.fake("Syncing cloud saves", item_id="saves:all", seconds=3, done_message="Up to date")
    from .launchers import LAUNCHERS
    targets = []
    for key in ("epic", "gog"):
        launcher = LAUNCHERS[key]
        try:
            ids = launcher.installed_ids() if launcher.available() else []
        except Exception:
            ids = []
        targets += [(key, ident, launcher) for ident in ids]
    job = jobs.begin("Syncing cloud saves", "saves:all", "Starting")

    def work():
        failed = 0
        for n, (key, ident, launcher) in enumerate(targets):
            job["message"] = ident
            try:
                ok = launcher.sync_saves(ident, "both")
            except Exception:
                ok = False
            _mark(f"{key}:{ident}", ok)
            failed += not ok
            job["progress"] = 100.0 * (n + 1) / len(targets)
        s = _load()
        s["last_sync"] = time.time()
        save_json(_path(), s)
        jobs.end(job, failed == 0, f"{failed} game{'s' if failed != 1 else ''} couldn't sync"
                 if failed else "Up to date")

    threading.Thread(target=work, daemon=True).start()
    return dict(job)


# --- Store specifics -----------------------------------------------------------


def legendary_sync(app_name, prefix, direction):
    if not have("legendary"):
        return False
    flags = {"down": ["--skip-upload"], "up": ["--skip-download"], "both": []}[direction]
    proc = subprocess.run(["legendary", "sync-saves", app_name, "-y", *flags],
                          capture_output=True, text=True, timeout=600,
                          env={**os.environ, "WINEPREFIX": str(prefix)})
    return proc.returncode == 0


def wine_user_dir(prefix):
    users = Path(prefix) / "drive_c" / "users"
    for name in ("steamuser", getpass.getuser()):
        if (users / name).is_dir():
            return users / name
    return users / "steamuser"


def gog_locations(game_dir, game_id, prefix):
    """GOG's cloud save folders for a game, resolved inside its prefix."""
    info = load_json(Path(game_dir) / f"goggame-{game_id}.info", {})
    client_id = info.get("clientId")
    if not client_id:
        return []
    cache = _load().setdefault("gog_config", {})
    config = cache.get(client_id)
    if config is None:
        url = f"https://remote-config.gog.com/components/galaxy_client/clients/{client_id}?component_version=2.0.45"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                cloud = json.load(resp).get("content", {}).get("Windows", {}).get("cloudStorage", {})
        except (OSError, ValueError):
            return []
        config = {"enabled": bool(cloud.get("enabled")), "locations": cloud.get("locations") or []}
        s = _load()
        s.setdefault("gog_config", {})[client_id] = config
        save_json(_path(), s)
    if not config["enabled"]:
        return []
    locations = config["locations"] or [{
        "name": "__default",
        "location": f"<?APPLICATION_DATA_LOCAL?>/GOG.com/Galaxy/Applications/{client_id}/Storage/Shared/Files",
    }]
    user = wine_user_dir(prefix)
    out = []
    for loc in locations:
        path = loc["location"].replace("\\", "/").replace("<?INSTALL?>", str(game_dir))
        for var, sub in GOG_VARS.items():
            path = path.replace(var, f"{user}/{sub}")
        if "<?" in path:
            continue  # a folder we don't know how to map
        out.append({"name": loc["name"], "path": path})
    return out


def gogdl_sync(auth, game_id, game_dir, prefix, direction):
    if not have("gogdl"):
        return False
    if not (Path(prefix) / "drive_c").is_dir():
        return True  # the prefix doesn't exist yet, so there's nothing to sync into
    flags = {"down": ["--skip-upload"], "up": ["--skip-download"], "both": []}[direction]
    s = _load()
    stamps = s.setdefault("gog_ts", {}).setdefault(str(game_id), {})
    ok = True
    for loc in gog_locations(game_dir, game_id, prefix):
        Path(loc["path"]).mkdir(parents=True, exist_ok=True)
        out = run(["gogdl", "--auth-config-path", auth, "save-sync", loc["path"], str(game_id),
                   "--os", "windows", "--ts", str(stamps.get(loc["name"], 0)), "--name", loc["name"],
                   *flags], timeout=600)
        # gogdl prints the new sync timestamp last; nothing means it failed.
        last = out.strip().splitlines()[-1] if out.strip() else ""
        try:
            stamps[loc["name"]] = float(last)
        except ValueError:
            ok = False
    s = {**_load(), "gog_ts": s["gog_ts"]}
    save_json(_path(), s)
    return ok
