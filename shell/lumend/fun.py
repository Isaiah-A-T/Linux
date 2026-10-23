"""The "fun" side of the top bar: music, screenshot album, theme."""

import urllib.parse
from pathlib import Path

from . import capture, mock
from .util import ApiError, data_dir, load_json, mock_enabled, run, save_json

ACCENTS = {
    "Mint": "#3ee6a0", "Azure": "#4da3ff", "Rose": "#ff6b8b",
    "Amber": "#ffb547", "Violet": "#b48cff", "Ice": "#36d6e7",
}
WALLPAPERS = ["aurora", "nebula", "grid", "dusk"]


def album_dirs():
    return [capture.shots_dir(), capture.clips_dir(), Path("/tmp")]


def album():
    if mock_enabled():
        return {"shots": [
            {"path": f"/api/mock-art/shot:{t}.svg?shape=hero", "title": t, "video": t == "Celeste"}
            for t in ("Hades", "Celeste", "Cyberpunk 2077", "Elden Ring", "Hollow Knight", "Valheim")
        ]}
    shots = []
    for d in album_dirs():
        if not d.is_dir():
            continue
        pattern = "gamescope_*.png" if str(d) == "/tmp" else "*.mp4" if d == capture.clips_dir() else "*.png"
        shots += d.glob(pattern)
    shots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return {"shots": [{"path": f"/api/shot?path={urllib.parse.quote(str(p))}", "title": p.stem,
                       "video": p.suffix == ".mp4"} for p in shots[:60]]}


def album_allowed(path):
    p = Path(path).resolve()
    if p.suffix == ".mp4":
        dirs = [capture.clips_dir()]
    elif p.suffix == ".png":
        dirs = [capture.shots_dir()]
        if p.parent == Path("/tmp") and p.name.startswith("gamescope_"):
            return True
    else:
        return False
    return any(p.is_relative_to(d.resolve()) for d in dirs if d.exists())


def media():
    if mock_enabled():
        return mock.state["media"]
    fmt = "{{status}}\t{{title}}\t{{artist}}\t{{playerName}}"
    out = run(["playerctl", "metadata", "--format", fmt]).strip()
    if not out:
        return {"available": False}
    status, title, artist, player = (out.split("\t") + ["", "", "", ""])[:4]
    return {"available": True, "playing": status == "Playing", "title": title,
            "artist": artist, "player": player}


def media_action(action):
    if action not in ("play-pause", "next", "previous"):
        raise ApiError("Unknown media action.")
    if mock_enabled():
        if action == "play-pause":
            mock.state["media"]["playing"] = not mock.state["media"]["playing"]
        return media()
    run(["playerctl", action])
    return media()


def _settings_path():
    return data_dir() / "settings.json"


def settings():
    s = load_json(_settings_path(), {})
    return {
        "accent": s.get("accent", ACCENTS["Mint"]),
        "wallpaper": s.get("wallpaper", "aurora"),
        "accents": ACCENTS,
        "wallpapers": WALLPAPERS,
    }


def update_settings(payload):
    s = load_json(_settings_path(), {})
    if payload.get("accent") in ACCENTS.values():
        s["accent"] = payload["accent"]
    if payload.get("wallpaper") in WALLPAPERS:
        s["wallpaper"] = payload["wallpaper"]
    save_json(_settings_path(), s)
    return settings()
