"""Settings › System update: update the installed system in place.

One job runs three steps: the OS and the Lumen shell through pacman (the
shell ships in the [lumen] repo that CI publishes), then the player's
Flatpak apps, then Snap apps. The pacman step needs root, so it goes through
pkexec to lumen-update-system; polkit lets admins (wheel) do that without a
password. Flatpaks from the Store are --user installs and Snap has its own
polkit action, so those two run as the player.

Automatic updates run as root from lumen-auto-update.timer (the same helper's
`auto` command). It writes how it got on to AUTO_STATUS, and holds LOCK while
it works; lumend reads both to show background updates in Settings and in
Notifications.
"""

import fcntl
import os
import re
import time
from datetime import datetime

from . import jobs, mock
from .util import ApiError, have, mock_enabled, run

HELPER = "/usr/lib/lumen/lumen-update-system"
JOB_ID = "system:update"
AUTO_JOB_ID = "system:auto-update"
PACMAN_LOG = "/var/log/pacman.log"
PACMAN_LOCAL = "/var/lib/pacman/local"
AUTO_CONF = "/etc/lumen/update.conf"
AUTO_STATUS = "/var/lib/lumen/auto-update"
LOCK = "/run/lumen-update.lock"
AUTO_MODES = ("install", "download", "off")
# The helper's states while it works; anything else is a finished run.
_AUTO_BUSY = ("checking", "downloading", "waiting", "installing")

# pacman's "(12/40) upgrading mesa" lines while it installs.
_PACMAN_STEP = re.compile(r"^\(\s*(\d+)/(\d+)\)\s+(?:upgrading|installing|reinstalling|downgrading|removing)\b")
_UPGRADE_START = re.compile(r"^\[([^\]]+)\] \[PACMAN\] starting full system upgrade")

_last_check = {"checked": None, "packages": [], "apps": 0, "error": None}


def parse_pacman_progress(line):
    """How far pacman is (0-1), from its install lines; None for other lines."""
    match = _PACMAN_STEP.match(line)
    if not match:
        return None
    done, total = int(match.group(1)), int(match.group(2))
    return done / total if total else None


def parse_pending(text):
    """Turn `pacman -Qu` lines ("mesa 1.0-1 -> 1.1-1") into dicts."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "->":
            out.append({"name": parts[0], "old": parts[1], "new": parts[3],
                        "ignored": "[ignored]" in line})
    return out


def last_upgrade(path=PACMAN_LOG):
    """When the last full system upgrade started, as a Unix time."""
    last = None
    try:
        with open(path, errors="replace") as f:
            for line in f:
                match = _UPGRADE_START.match(line)
                if match:
                    last = match.group(1)
    except OSError:
        return None
    # pacman 5.1 and later write ISO 8601; older logs use "2019-01-01 12:00".
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(last or "", fmt).timestamp()
        except ValueError:
            continue
    return None


def parse_auto_status(text):
    """The helper's key=value status file as a dict, with numbers as numbers."""
    out = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key.strip()] = value.strip()
    for key in ("time", "count"):
        try:
            out[key] = int(out.get(key) or 0)
        except ValueError:
            out[key] = 0
    return out


def auto_mode(path=AUTO_CONF):
    """AUTO_UPDATE from update.conf: install (the default), download or off."""
    try:
        with open(path) as f:
            for line in f:
                match = re.match(r"\s*AUTO_UPDATE=[\"']?(\w+)", line)
                if match and match.group(1) in AUTO_MODES:
                    return match.group(1)
    except OSError:
        pass
    return "install"


def _update_locked():
    """True while the helper holds its lock (an update is downloading or installing)."""
    try:
        fd = os.open(LOCK, os.O_RDONLY)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def auto_status():
    if mock_enabled():
        return dict(mock.state["update"]["auto"])
    try:
        with open(AUTO_STATUS) as f:
            st = parse_auto_status(f.read())
    except OSError:
        st = {"state": "", "time": 0, "count": 0, "message": ""}
    # A run that was cut off (turned off while waiting) leaves a busy state behind.
    st["running"] = st.get("state") in _AUTO_BUSY and _update_locked()
    if st.get("state") in _AUTO_BUSY and not st["running"]:
        st["state"] = ""
    st["mode"] = auto_mode()
    return st


def _local_version(name):
    """The installed version of a package, from pacman's local database."""
    try:
        entries = os.listdir(PACMAN_LOCAL)
    except OSError:
        return None
    prefix = name + "-"
    for entry in entries:
        # Entries are name-pkgver-pkgrel; pkgver never contains "-".
        if entry.startswith(prefix) and entry[len(prefix):].count("-") == 1:
            return entry[len(prefix):]
    return None


def is_ps5():
    return _local_version("linux-ps5") is not None


# The shell this lumend started with; a newer installed one needs a restart.
_started_with = _local_version("lumen")


def reboot_needed():
    """True when an update replaced the running kernel or shell."""
    if mock_enabled():
        return mock.state["update"]["reboot"]
    return (not os.path.isdir(f"/usr/lib/modules/{os.uname().release}")
            or _local_version("lumen") != _started_with)


def background_jobs():
    """Automatic updates, shaped like jobs for the Notifications blade."""
    st = auto_status()
    out = []
    if st["running"] and st["state"] in ("downloading", "installing"):
        n = st["count"]
        out.append({"id": "auto-update", "title": "System update", "item_id": AUTO_JOB_ID,
                    "state": "running", "progress": 0.0, "started": st["time"],
                    "message": (f"Downloading {n} update{'s' if n != 1 else ''}" if st["state"] == "downloading"
                                else "Installing in the background")})
    elif reboot_needed():
        out.append({"id": "auto-update", "title": "System update", "item_id": AUTO_JOB_ID,
                    "state": "done", "progress": 100.0, "started": st["time"],
                    "message": restart_hint()})
    return out


def restart_hint():
    # Restarting a PS5 drops it back into the PS5 system software.
    if is_ps5():
        return "Turn Lumen off, then start it again from your PS5 to finish updating"
    return "Restart to finish updating"


def set_auto(payload):
    mode = (payload or {}).get("mode")
    if mode not in AUTO_MODES:
        raise ApiError("Unknown automatic update setting.")
    _require_installed()
    if mock_enabled():
        mock.state["update"]["auto"]["mode"] = mode
        return status()
    try:
        run(["pkexec", HELPER, "set-auto", mode], timeout=60, check=True)
    except RuntimeError:
        raise ApiError("Only an administrator can change automatic updates.")
    return status()


def installing():
    """True while pacman is changing the system; turning off now could break it."""
    if mock_enabled():
        return bool(_running_job())
    # The helper's lock too, so a db.lck left behind by a crash doesn't count.
    return os.path.exists("/var/lib/pacman/db.lck") and _update_locked()


def _running_job():
    return next((j for j in jobs.all_jobs() if j["item_id"] == JOB_ID and j["state"] == "running"), None)


def _require_installed():
    from .server import is_live
    if is_live():
        raise ApiError("Install Lumen OS first. The live system resets when it restarts.")


def status():
    if mock_enabled():
        return {**mock.state["update"], "job": _running_job(), "restart_hint": restart_hint()}
    return {
        "available": os.path.exists(HELPER) and have("pkexec"),
        "last_upgrade": last_upgrade(),
        "job": _running_job(),
        "auto": auto_status(),
        "reboot": reboot_needed(),
        "ps5": is_ps5(),
        "restart_hint": restart_hint(),
        **_last_check,
    }


def check():
    _require_installed()
    if mock_enabled():
        time.sleep(1.5)
        mock.state["update"]["checked"] = time.time()
        return status()
    try:
        out = run(["pkexec", HELPER, "check"], timeout=180, check=True)
    except RuntimeError as exc:
        _last_check["error"] = str(exc)
        return status()
    _last_check["packages"] = parse_pending(out)
    _last_check["error"] = None
    apps = 0
    if have("flatpak"):
        apps += len([l for l in run(["flatpak", "remote-ls", "--user", "--updates", "--app",
                                     "--columns=application"], timeout=60).splitlines() if l.strip()])
    if have("snap"):
        # "All snaps up to date." goes to stderr, so stdout is the header plus one line per snap.
        apps += max(0, len(run(["snap", "refresh", "--list"], timeout=60).splitlines()) - 1)
    _last_check["apps"] = apps
    _last_check["checked"] = time.time()
    return status()


def start():
    _require_installed()
    if _running_job():
        raise ApiError("An update is already running.")
    if auto_status()["running"] and auto_status()["state"] == "installing":
        raise ApiError("Lumen is already installing updates in the background.")
    if mock_enabled():
        mock.state["update"]["packages"] = []
        mock.state["update"]["apps"] = 0
        mock.state["update"]["last_upgrade"] = time.time()
        return jobs.fake("System update", item_id=JOB_ID, seconds=8, done_message="Up to date",
                         done_extra={"reboot": True})
    if not os.path.exists(HELPER):
        raise ApiError("The update helper is missing. Reinstall the lumen package.")

    steps = [("System and Lumen", ["pkexec", HELPER, "upgrade"], 8, parse_pacman_progress)]
    if have("flatpak"):
        steps.append(("Flatpak apps", ["flatpak", "update", "--user", "--noninteractive", "-y"], 1, jobs.percent))
    if have("snap"):
        steps.append(("Snap apps", ["snap", "refresh"], 1, None))

    def done(job):
        if not any(job["codes"]):
            _last_check.update(packages=[], apps=0, checked=time.time())
        # pkexec exits 126/127 when polkit says no (not an admin, or no agent).
        if job["codes"] and job["codes"][0] in (126, 127):
            job["message"] = "Only an administrator can install system updates."
        # A new kernel removes the running one's modules; a new shell needs lumend restarted.
        job["reboot"] = reboot_needed()

    return jobs.start_steps("System update", steps, on_done=done, item_id=JOB_ID)

