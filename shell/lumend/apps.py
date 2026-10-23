"""Regular desktop apps, read from .desktop files (pacman, Flatpak and Snap)."""

import configparser
import os
import shlex
import subprocess
from pathlib import Path

from .util import session_env

_FIELD_CODES = {"%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N", "%i", "%c", "%k", "%v", "%m"}

# Our own session tools and launchers we wrap ourselves stay out of the list.
_HIDE = {"lumen", "steam", "legendary", "gogdl", "chromium-browser", "avahi-discover",
         "bssh", "bvnc", "qv4l2", "qvidcap", "lstopo"}


def data_dirs():
    home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs = [home, *system.split(":"),
            os.path.expanduser("~/.local/share/flatpak/exports/share"),
            "/var/lib/flatpak/exports/share", "/var/lib/snapd/desktop"]
    seen, out = set(), []
    for d in dirs:
        if d and d not in seen:
            seen.add(d)
            out.append(Path(d))
    return out


def icon_roots():
    roots = []
    for d in data_dirs():
        roots += [d / "icons", d / "pixmaps"]
    roots.append(Path("/usr/share/pixmaps"))
    return roots


def find_icon(name):
    """Resolve an Icon= value to a file, preferring large hicolor PNG/SVG."""
    if not name:
        return None
    if os.path.isabs(name):
        return name if os.path.exists(name) else None
    sizes = ["scalable", "512x512", "256x256", "192x192", "128x128", "96x96", "64x64", "48x48"]
    for root in icon_roots():
        for theme in ("hicolor", "Adwaita", "breeze"):
            for size in sizes:
                for ext in (".svg", ".png"):
                    p = root / theme / size / "apps" / f"{name}{ext}"
                    if p.exists():
                        return str(p)
        for ext in (".svg", ".png", ".xpm"):
            p = root / f"{name}{ext}"
            if p.exists():
                return str(p)
    return None


def parse_desktop(path):
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    e = cp["Desktop Entry"]
    if e.get("Type") != "Application" or e.get("NoDisplay") == "true" or e.get("Hidden") == "true":
        return None
    if e.get("OnlyShowIn") and "Lumen" not in e.get("OnlyShowIn", ""):
        return None
    exec_line = e.get("Exec")
    if not exec_line or e.get("Terminal") == "true":
        return None
    return {
        "desktop_id": Path(path).stem,
        "name": e.get("Name", Path(path).stem),
        "comment": e.get("Comment", ""),
        "exec": exec_line,
        "icon": e.get("Icon", ""),
        "categories": [c for c in e.get("Categories", "").split(";") if c],
    }


def _source_for(path):
    p = str(path)
    if "/flatpak/" in p:
        return "flatpak"
    if "/snapd/" in p:
        return "snap"
    return "system"


def list_apps():
    """All launchable apps; a desktop id found twice keeps the first (user) one."""
    found = {}
    for d in data_dirs():
        appdir = d / "applications"
        if not appdir.is_dir():
            continue
        for path in sorted(appdir.rglob("*.desktop")):
            entry = parse_desktop(path)
            if entry is None or entry["desktop_id"] in found:
                continue
            if entry["desktop_id"].lower().split(".")[-1] in _HIDE or entry["desktop_id"].lower() in _HIDE:
                continue
            if "steam://rungameid" in entry["exec"]:
                continue  # Steam game shortcuts; the Steam source lists those
            icon = find_icon(entry["icon"])
            art = {"icon": f"/api/icon?path={icon}"} if icon else {}
            found[entry["desktop_id"]] = {
                "id": f"app:{entry['desktop_id']}",
                "title": entry["name"],
                "subtitle": entry["comment"],
                "source": "app",
                "package": _source_for(path),
                "kind": "game" if "Game" in entry["categories"] else "app",
                "installed": True,
                "art": art,
                "_exec": entry["exec"],
            }
    return sorted(found.values(), key=lambda a: a["title"].lower())


def exec_args(exec_line):
    return [a for a in shlex.split(exec_line) if a not in _FIELD_CODES]


def launch(item, env=None):
    return subprocess.Popen(exec_args(item["_exec"]), env=session_env(env), start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
