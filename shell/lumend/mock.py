"""Fake system state and library used when LUMEN_MOCK=1 (UI development)."""

import hashlib
import time
from html import escape

state = {
    "wifi": {
        "available": True,
        "enabled": True,
        "networks": [
            {"ssid": "Home Network", "signal": 86, "secure": True, "connected": True},
            {"ssid": "Upstairs 5G", "signal": 64, "secure": True, "connected": False},
            {"ssid": "Coffee Shop", "signal": 41, "secure": False, "connected": False},
            {"ssid": "Neighbour", "signal": 22, "secure": True, "connected": False},
        ],
    },
    "bluetooth": {
        "available": True,
        "enabled": True,
        "devices": [
            {"address": "AA:BB:CC:00:00:01", "name": "Wireless Controller", "paired": True, "connected": True},
            {"address": "AA:BB:CC:00:00:02", "name": "Headphones", "paired": True, "connected": False},
            {"address": "AA:BB:CC:00:00:03", "name": "Keyboard K380", "paired": False, "connected": False},
        ],
    },
    "audio": {"volume": 60, "muted": False},
    "brightness": {"available": True, "level": 80},
    "battery": {"present": True, "level": 72, "charging": False},
    "airplane": False,
    "media": {
        "available": True,
        "playing": True,
        "title": "Midnight Drive",
        "artist": "Synth Collective",
        "player": "Spotify",
    },
}

_now = time.time()

# (id, title, source, kind, installed, hours ago last played)
_LIBRARY = [
    ("steam:1145360", "Hades", "steam", "game", True, 2),
    ("epic:Satisfactory", "Satisfactory", "epic", "game", True, 5),
    ("steam:1091500", "Cyberpunk 2077", "steam", "game", True, 20),
    ("gog:1207664663", "The Witcher 3", "gog", "game", True, 30),
    ("app:org.mozilla.firefox", "Firefox", "app", "app", True, 34),
    ("steam:504230", "Celeste", "steam", "game", True, 50),
    ("app:com.spotify.Client", "Spotify", "app", "app", True, 60),
    ("epic:Rocket League", "Rocket League", "epic", "game", True, 80),
    ("steam:413150", "Stardew Valley", "steam", "game", True, 90),
    ("app:com.discordapp.Discord", "Discord", "app", "app", True, 100),
    ("gog:1423049311", "Cyber Shadow", "gog", "game", True, 120),
    ("steam:367520", "Hollow Knight", "steam", "game", True, 150),
    ("app:org.videolan.VLC", "VLC", "app", "app", True, 200),
    ("steam:1245620", "Elden Ring", "steam", "game", True, 260),
    ("epic:Control", "Control", "epic", "game", True, 300),
    ("steam:620", "Portal 2", "steam", "game", True, 400),
    ("app:com.obsproject.Studio", "OBS Studio", "app", "app", True, 500),
    ("steam:892970", "Valheim", "steam", "game", False, None),
    ("epic:Alan Wake 2", "Alan Wake 2", "epic", "game", False, None),
    ("gog:1207658924", "Frostpunk", "gog", "game", False, None),
    ("gog:1207666893", "Disco Elysium", "gog", "game", False, None),
    ("steam:1086940", "Baldur's Gate 3", "steam", "game", False, None),
    ("app:org.libreoffice.LibreOffice", "LibreOffice", "app", "app", True, None),
    ("app:org.gimp.GIMP", "GIMP", "app", "app", True, None),
]


def library():
    items = []
    for item_id, title, source, kind, installed, hours in _LIBRARY:
        items.append({
            "id": item_id,
            "title": title,
            "source": source,
            "kind": kind,
            "installed": installed,
            "last_played": _now - hours * 3600 if hours is not None else None,
            "art": {
                "cover": f"/api/mock-art/{item_id}.svg?shape=cover",
                "hero": f"/api/mock-art/{item_id}.svg?shape=hero",
                "icon": f"/api/mock-art/{item_id}.svg?shape=icon",
            },
        })
    return items


accounts = {
    "steam": {"connected": True, "user": "fenta_plays"},
    "epic": {"connected": True, "user": "Fenta"},
    "gog": {"connected": False, "user": None},
}

_PALETTES = [
    ("#ff5f6d", "#3a0ca3"), ("#00c9ff", "#1b2a49"), ("#f7971e", "#5c2a9d"),
    ("#43e97b", "#0f3443"), ("#fa709a", "#30cfd0"), ("#b721ff", "#21d4fd"),
    ("#ff9a8b", "#4b1248"), ("#13f1fc", "#0470dc"), ("#f9d423", "#e14fad"),
]


def art_svg(key, shape="cover"):
    """Generated placeholder artwork: a gradient with the title on it."""
    title = key.split(":")[1] if key.count(":") >= 1 else key
    for item_id, name, *_ in _LIBRARY:
        if item_id == key:
            title = name
            break
    digest = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    a, b = _PALETTES[digest % len(_PALETTES)]
    angle = digest % 360
    w, h = {"cover": (600, 900), "hero": (1920, 620), "icon": (256, 256)}.get(shape, (600, 900))
    size = {"cover": 64, "hero": 120, "icon": 110}.get(shape, 64)
    label = escape(title if shape != "icon" else "".join(w[0] for w in title.split()[:2]).upper())
    cx, cy = (w // 2, h // 2) if shape != "hero" else (int(w * 0.72), h // 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs><linearGradient id="g" gradientTransform="rotate({angle} .5 .5)">
<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>
<radialGradient id="r" cx=".3" cy=".2" r=".9"><stop offset="0" stop-color="#fff" stop-opacity=".35"/>
<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>
<rect width="100%" height="100%" fill="url(#g)"/>
<circle cx="{w * 0.85:.0f}" cy="{h * 0.2:.0f}" r="{min(w, h) * 0.55:.0f}" fill="#fff" opacity=".07"/>
<circle cx="{w * 0.1:.0f}" cy="{h * 0.95:.0f}" r="{min(w, h) * 0.45:.0f}" fill="#000" opacity=".12"/>
<rect width="100%" height="100%" fill="url(#r)"/>
<text x="{cx}" y="{cy}" fill="#fff" font-family="Inter, system-ui, sans-serif" font-weight="800"
 font-size="{size}" text-anchor="middle" dominant-baseline="middle"
 style="letter-spacing:-1px">{label}</text></svg>"""


STORE_APPS = [
    ("flatpak", "org.mozilla.firefox", "Firefox", "Fast, private and safe web browser", "Mozilla"),
    ("flatpak", "com.spotify.Client", "Spotify", "Online music streaming service", "Spotify"),
    ("flatpak", "com.discordapp.Discord", "Discord", "Messaging, voice and video for gamers", "Discord"),
    ("flatpak", "org.videolan.VLC", "VLC", "Play any media file", "VideoLAN"),
    ("flatpak", "com.obsproject.Studio", "OBS Studio", "Live streaming and video recording", "OBS Project"),
    ("snap", "code", "Visual Studio Code", "Code editing. Redefined.", "Microsoft"),
    ("flatpak", "net.lutris.Lutris", "Lutris", "Open gaming platform", "Lutris"),
    ("flatpak", "org.libreoffice.LibreOffice", "LibreOffice", "The office suite", "The Document Foundation"),
    ("flatpak", "org.gimp.GIMP", "GIMP", "Create images and edit photographs", "GIMP team"),
    ("snap", "telegram-desktop", "Telegram", "Fast and secure messaging", "Telegram FZ-LLC"),
    ("flatpak", "com.valvesoftware.Steam.CompatibilityTool.Proton-GE", "Proton GE", "Proton with extra patches", "GloriousEggroll"),
    ("snap", "plex-desktop", "Plex", "Stream your media library", "Plex"),
    ("flatpak", "tv.kodi.Kodi", "Kodi", "Media center for your TV", "Kodi team"),
    ("flatpak", "org.prismlauncher.PrismLauncher", "Prism Launcher", "Minecraft launcher", "Prism team"),
    ("snap", "slack", "Slack", "Team communication", "Slack"),
    ("flatpak", "io.github.retroarch", "RetroArch", "Frontend for emulators and games", "Libretro"),
]
