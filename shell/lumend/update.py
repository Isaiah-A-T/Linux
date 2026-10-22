"""Settings › System update: update the installed system in place.

One job runs three steps: the OS and the Lumen shell through pacman (the
shell ships in the [lumen] repo that CI publishes), then the player's
Flatpak apps, then Snap apps. The pacman step needs root, so it goes through
pkexec to lumen-update-system; polkit lets admins (wheel) do that without a
password. Flatpaks from the Store are --user installs and Snap has its own
polkit action, so those two run as the player.
"""

import os
import re
import time
from datetime import datetime

from . import jobs, mock
from .util import ApiError, have, mock_enabled, run

HELPER = "/usr/lib/lumen/lumen-update-system"
JOB_ID = "system:update"
PACMAN_LOG = "/var/log/pacman.log"

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


def _running_job():
    return next((j for j in jobs.all_jobs() if j["item_id"] == JOB_ID and j["state"] == "running"), None)


def _require_installed():
    from .server import is_live
    if is_live():
        raise ApiError("Install Lumen OS first. The live system resets when it restarts.")


def status():
    if mock_enabled():
        return {**mock.state["update"], "job": _running_job()}
    return {
        "available": os.path.exists(HELPER) and have("pkexec"),
        "last_upgrade": last_upgrade(),
        "job": _running_job(),
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
    before = run(["pacman", "-Q", "lumen"])

    def done(job):
        if not any(job["codes"]):
            _last_check.update(packages=[], apps=0, checked=time.time())
        # pkexec exits 126/127 when polkit says no (not an admin, or no agent).
        if job["codes"] and job["codes"][0] in (126, 127):
            job["message"] = "Only an administrator can install system updates."
        # A new kernel removes the running one's modules; a new shell needs lumend restarted.
        job["reboot"] = (run(["pacman", "-Q", "lumen"]) != before
                         or not os.path.isdir(f"/usr/lib/modules/{os.uname().release}"))

    return jobs.start_steps("System update", steps, on_done=done, item_id=JOB_ID)

