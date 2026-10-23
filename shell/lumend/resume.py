"""Quick Resume: games keep their place in the background, paused.

Going Home (the Guide button, or starting something else) pauses the game on
screen with SIGSTOP on its whole process tree. It then uses no CPU or GPU
time but stays in memory, exactly where it was. Picking it again sends
SIGCONT and brings its window back. Up to LIMIT games stay paused at once;
starting one more closes the one paused longest ago, like on Xbox.

Sleep keeps everything in memory too, so paused games survive it. They do not
survive a restart or signing out.

Apps aren't paused (music and downloads should keep going), but they are
tracked, so Home can switch back to them.

Each entry knows its processes by session id: lumend starts every game and
app with start_new_session, and Wine's helpers stay in that session. Steam
starts its games itself, so for those we find Steam's launch wrapper
("reaper ... AppId=<id>") and take everything below it.
"""

import os
import signal
import threading
import time

from . import gamescope
from .util import mock_enabled

LIMIT = 3
STEAM_GRACE = 180  # Steam may update the game before starting it

_lock = threading.RLock()
_entries = {}  # item id -> entry
_front = {"id": None}  # what's on screen; None is the shell


def processes():
    """{pid: (ppid, sid, state)} for every process we can see."""
    out = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                stat = f.read()
        except OSError:
            continue
        fields = stat.rpartition(")")[2].split()
        # state ppid pgrp session ...
        out[int(name)] = (int(fields[1]), int(fields[3]), fields[0])
    return out


def _cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().split(b"\0")
    except OSError:
        return []


def steam_root(appid, procs):
    """The pid of Steam's launch wrapper for appid, or None."""
    want = f"AppId={appid}".encode()
    for pid in procs:
        args = _cmdline(pid)
        if want in args and any(a.endswith(b"reaper") for a in args):
            return pid
    return None


def members(entry, procs):
    """Live pids belonging to an entry (its session plus everything below its root)."""
    root, sid = entry.get("pid"), entry.get("sid")
    if root is None and entry.get("steam_appid"):
        root = steam_root(entry["steam_appid"], procs)
        if root is not None:
            entry["pid"] = root
    found = {pid for pid, (_pp, s, _st) in procs.items() if sid is not None and s == sid}
    if root in procs:
        found.add(root)
    children = {}
    for pid, (ppid, _s, _st) in procs.items():
        children.setdefault(ppid, []).append(pid)
    todo = list(found)
    while todo:
        for child in children.get(todo.pop(), []):
            if child not in found:
                found.add(child)
                todo.append(child)
    return {pid for pid in found if procs[pid][2] != "Z" and pid != os.getpid()}


def _signal(entry, sig):
    if mock_enabled():
        return
    for pid in members(entry, processes()):
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def _public(entry):
    return {k: entry[k] for k in ("id", "title", "kind", "source", "art", "state", "started", "paused_at")}


def status():
    with _lock:
        _prune()
        items = sorted(_entries.values(), key=lambda e: e["started"], reverse=True)
        return {"front": _front["id"], "limit": LIMIT, "items": [_public(e) for e in items]}


def get(item_id):
    with _lock:
        return _entries.get(item_id)


def _prune():
    """Forget games that have quit."""
    if mock_enabled():
        return
    procs = processes()
    for item_id, entry in list(_entries.items()):
        if members(entry, procs):
            continue
        if entry["pid"] is None and (entry.get("steam_appid") or entry.get("pending")) \
                and time.time() - entry["started"] < STEAM_GRACE:
            continue  # Steam, or a cloud save download, hasn't started it yet
        del _entries[item_id]
        if _front["id"] == item_id:
            _front["id"] = None
            gamescope.show_shell()


def _pause(entry):
    if entry["kind"] != "game" or entry["state"] == "paused":
        return
    _signal(entry, signal.SIGSTOP)
    entry["state"] = "paused"
    entry["paused_at"] = time.time()


def _make_room():
    """Close the games paused longest ago until there's room for one more."""
    closed = []
    paused = sorted((e for e in _entries.values() if e["state"] == "paused"), key=lambda e: e["paused_at"])
    while paused and len(paused) >= LIMIT:
        entry = paused.pop(0)
        _close(entry)
        closed.append(entry["title"])
    return closed


def started(item, proc):
    """Record a game or app lumend just started. Returns titles it had to close."""
    with _lock:
        if mock_enabled():
            # There's no real game in a browser: show it as if you'd played
            # and come back Home, so the UI can be tried out.
            closed = _make_room() if item["kind"] == "game" else []
            _entries[item["id"]] = _entry(item, None, "paused")
            return closed
        _prune()
        _leave_front()
        closed = _make_room() if item["kind"] == "game" else []
        # Let gamescope show new windows as they come (Steam's own dialogs,
        # launchers, splash screens); _keep_front pins the game's window.
        gamescope.release()
        pid = proc.pid if proc else None
        entry = _entry(item, pid, "running")
        if item["source"] == "steam":
            entry["steam_appid"] = item["id"].partition(":")[2]
        elif proc is None:
            entry["pending"] = True  # cloud saves download first; see attach()
        _entries[item["id"]] = entry
        _front["id"] = item["id"]
        return closed


def attach(item_id, proc):
    """Give a game started late (after its cloud saves came down) its process."""
    with _lock:
        entry = _entries.get(item_id)
        if entry is None or not entry.pop("pending", False):
            return
        entry["pid"] = entry["sid"] = proc.pid
        if entry["state"] == "paused":  # left for Home while the saves synced
            _signal(entry, signal.SIGSTOP)


def _entry(item, pid, state):
    now = time.time()
    return {"id": item["id"], "title": item["title"], "kind": item.get("kind", "game"),
            "source": item.get("source"), "art": item.get("art", {}), "pid": pid, "sid": pid,
            "state": state, "started": now, "paused_at": now if state == "paused" else None}


def _leave_front():
    entry = _entries.get(_front["id"])
    if entry:
        _pause(entry)
    _front["id"] = None


def resume(item_id):
    """Unpause a game (or switch back to an app) and put it on screen."""
    with _lock:
        _prune()
        entry = _entries.get(item_id)
        if entry is None:
            return None
        if _front["id"] != item_id:
            _leave_front()
        _signal(entry, signal.SIGCONT)
        entry["state"] = "running"
        entry["paused_at"] = None
        if mock_enabled():
            # Same as started(): back Home straight away.
            _pause(entry)
            return _public(entry)
        _front["id"] = item_id
        if not gamescope.show(members(entry, processes())):
            gamescope.release()
        return _public(entry)


def go_home():
    """Pause whatever is on screen and show the shell."""
    with _lock:
        if _front["id"] is None:
            return False
        _leave_front()
        gamescope.show_shell()
        return True


def _close(entry):
    _entries.pop(entry["id"], None)
    if _front["id"] == entry["id"]:
        _front["id"] = None
        gamescope.show_shell()
    if mock_enabled():
        return
    pids = members(entry, processes())

    def stop():
        for sig in (signal.SIGCONT, signal.SIGTERM):
            for pid in pids:
                try:
                    os.kill(pid, sig)
                except OSError:
                    pass
        time.sleep(5)
        for pid in members(entry, processes()):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    threading.Thread(target=stop, daemon=True).start()


def close(item_id):
    with _lock:
        entry = _entries.get(item_id)
        if entry:
            _close(entry)
        return status()


def before_sleep():
    """Sleep keeps paused games in memory; pause the one on screen first."""
    go_home()


def _keep_front():
    """Keep the game's window up: launchers often swap windows (splash, then
    game), and a window that closes would otherwise leave the shell showing."""
    while True:
        time.sleep(1)
        try:
            with _lock:
                _prune()
                entry = _entries.get(_front["id"])
                if entry is None:
                    continue
                pids = members(entry, processes())
                mine = [w for w, _a, pid in gamescope.windows() if pid in pids]
                if mine and gamescope.shown() not in mine:
                    gamescope.show(pids)
        except Exception:  # the loop must survive anything odd in /proc or xprop
            continue


def start(library_items=None):
    """Start the background watchers (session mode, real hardware only).

    In mock mode, show the first game of the mock library as paused instead.
    """
    if mock_enabled():
        game = next((i for i in library_items or [] if i["kind"] == "game"), None)
        if game:
            started(game, None)
        return
    from . import pads
    pads.watch(go_home)
    threading.Thread(target=_keep_front, name="quick-resume", daemon=True).start()
