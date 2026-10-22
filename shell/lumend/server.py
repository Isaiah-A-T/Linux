"""HTTP server: the JSON API under /api and the static UI everywhere else."""

import json
import mimetypes
import os
import subprocess
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__, apps, art, fun, jobs, library, mock, store, system, users
from .util import ApiError, mock_enabled


def is_live():
    # The PS5 USB image counts as live until its first-boot setup has run.
    return (os.path.isdir("/run/archiso") or os.path.exists("/var/lib/lumen/setup-pending")
            or os.environ.get("LUMEN_LIVE") == "1")


def _info(_q, _b):
    return {"version": __version__, "mock": mock_enabled(), "live": is_live(),
            "mode": Handler.mode}


def _about(_q, _b):
    import platform
    import shutil
    from .util import games_dir
    disks = []
    for label, path in (("System", "/"), ("Games", str(games_dir()))):
        try:
            u = shutil.disk_usage(path)
        except OSError:
            continue
        if any(d["total"] == u.total and d["used"] == u.used for d in disks):
            continue  # same filesystem
        disks.append({"label": label, "path": path, "total": u.total, "used": u.used})
    return {"version": __version__, "kernel": platform.release(), "hostname": platform.node(),
            "disks": disks}


def _install_os(_q, _b):
    if not is_live():
        raise ApiError("Lumen OS is already installed.")
    if not mock_enabled():
        subprocess.Popen(["lumen-installer"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}


# (method, path) -> handler(query, body). Kept as one table so the whole API
# is readable in one place.
ROUTES = {
    ("GET", "/api/ping"): lambda q, b: {"ok": True},
    ("GET", "/api/info"): _info,
    ("GET", "/api/about"): _about,
    ("GET", "/api/me"): lambda q, b: users.me(),
    ("GET", "/api/home"): lambda q, b: {"items": library.home()},

    ("GET", "/api/quick"): lambda q, b: system.quick_settings(),
    ("POST", "/api/wifi"): lambda q, b: system.wifi_set_enabled(b.get("enabled")),
    ("POST", "/api/wifi/scan"): lambda q, b: system.wifi_state(rescan=True),
    ("POST", "/api/wifi/connect"): lambda q, b: system.wifi_connect(b["ssid"], b.get("password")),
    ("POST", "/api/wifi/disconnect"): lambda q, b: system.wifi_disconnect(b["ssid"]),
    ("POST", "/api/bluetooth"): lambda q, b: system.bluetooth_set_enabled(b.get("enabled")),
    ("POST", "/api/bluetooth/scan"): lambda q, b: system.bluetooth_scan(),
    ("POST", "/api/bluetooth/connect"): lambda q, b: system.bluetooth_connect(b["address"]),
    ("POST", "/api/bluetooth/disconnect"): lambda q, b: system.bluetooth_disconnect(b["address"], b.get("forget", False)),
    ("POST", "/api/audio"): lambda q, b: system.audio_set(b.get("volume"), b.get("muted")),
    ("POST", "/api/brightness"): lambda q, b: system.brightness_set(b["level"]),
    ("POST", "/api/airplane"): lambda q, b: system.airplane_set(b.get("enabled")),
    ("POST", "/api/power"): lambda q, b: system.power(b.get("action")),
    ("POST", "/api/install-os"): _install_os,

    ("GET", "/api/library"): lambda q, b: library.overview(),
    ("POST", "/api/library/refresh"): lambda q, b: (library.items(refresh=True), library.overview())[1],
    ("POST", "/api/library/launch"): lambda q, b: library.launch(b["id"]),
    ("POST", "/api/library/install"): lambda q, b: library.install(b["id"]),
    ("POST", "/api/library/uninstall"): lambda q, b: library.uninstall(b["id"]),
    ("GET", "/api/accounts"): lambda q, b: {"accounts": library.accounts()},
    ("POST", "/api/accounts/connect"): lambda q, b: {"accounts": library.connect(b["launcher"], b)},
    ("POST", "/api/accounts/disconnect"): lambda q, b: {"accounts": library.disconnect(b["launcher"])},
    ("POST", "/api/open-url"): lambda q, b: library.open_url(b["url"]),

    ("GET", "/api/store/featured"): lambda q, b: store.featured(),
    ("GET", "/api/store/search"): lambda q, b: store.search(q.get("q", "")),
    ("GET", "/api/store/app"): lambda q, b: store.details(q.get("source"), q.get("id")),
    ("POST", "/api/store/install"): lambda q, b: store.install(b["source"], b["id"]),
    ("POST", "/api/store/remove"): lambda q, b: store.remove(b["source"], b["id"]),

    ("GET", "/api/jobs"): lambda q, b: {"jobs": jobs.all_jobs()},

    ("GET", "/api/media"): lambda q, b: fun.media(),
    ("POST", "/api/media"): lambda q, b: fun.media_action(b.get("action")),
    ("GET", "/api/album"): lambda q, b: fun.album(),
    ("GET", "/api/settings"): lambda q, b: fun.settings(),
    ("POST", "/api/settings"): lambda q, b: fun.update_settings(b),

    ("GET", "/api/users"): lambda q, b: {"users": users.list_users()},
    ("POST", "/api/login"): lambda q, b: users.login(b["username"], b.get("secret", "")),
}

# The greeter runs as an unprivileged user before anyone signs in, so it gets
# only what the sign-in screen needs.
GREETER_ROUTES = {"/api/ping", "/api/info", "/api/users", "/api/login", "/api/quick",
                  "/api/power", "/api/wifi", "/api/wifi/connect", "/api/settings"}


class Handler(BaseHTTPRequestHandler):
    ui_root = Path(".")
    mode = "session"
    server_version = "lumend"

    def log_message(self, fmt, *args):
        if os.environ.get("LUMEN_DEBUG"):
            super().log_message(fmt, *args)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        url = urllib.parse.urlsplit(self.path)
        query = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
        path = url.path
        if not path.startswith("/api/"):
            return self._static(path)
        # Only the shell itself may call the API (blocks other local pages).
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
            return self._json({"error": "forbidden"}, 403)
        if self.mode == "greeter" and path not in GREETER_ROUTES and not path.startswith("/api/avatar/"):
            return self._json({"error": "not available on the sign-in screen"}, 403)
        try:
            if method == "GET" and path.startswith("/api/mock-art/"):
                key = urllib.parse.unquote(path[len("/api/mock-art/"):]).removesuffix(".svg")
                return self._bytes(mock.art_svg(key, query.get("shape", "cover")).encode(), "image/svg+xml")
            if method == "GET" and path == "/api/art":
                return self._art(urllib.parse.parse_qs(url.query))
            if method == "GET" and path == "/api/placeholder-art":
                svg = mock.art_svg(query.get("key", ""), query.get("shape", "cover"), query.get("title"))
                return self._bytes(svg.encode(), "image/svg+xml", cache=True)
            if method == "GET" and path == "/api/icon":
                return self._file(query.get("path", ""), allowed=apps.icon_roots())
            if method == "GET" and path == "/api/shot":
                if not fun.album_allowed(query.get("path", "")):
                    raise ApiError("Not found", 404)
                return self._file(query["path"])
            if method == "GET" and path.startswith("/api/avatar/"):
                return self._file(users.avatar_path(path.rsplit("/", 1)[-1]) or "")
            handler = ROUTES.get((method, path))
            if handler is None:
                raise ApiError("Not found", 404)
            body = {}
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            self._json(handler(query, body))
        except ApiError as exc:
            self._json({"error": str(exc)}, exc.status)
        except KeyError as exc:
            self._json({"error": f"missing field {exc}"}, 400)
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": str(exc) or exc.__class__.__name__}, 500)

    def _json(self, value, status=200):
        self._bytes(json.dumps(value, default=list).encode(), "application/json", status)

    def _bytes(self, data, ctype, status=200, cache=False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _art(self, params):
        got = art.first_image(params.get("u", []))
        if got:
            return self._bytes(got[0], got[1], cache=True)
        fallback = params.get("f", [""])[-1]
        if not fallback.startswith("/api/placeholder-art?"):
            raise ApiError("Not found", 404)
        self.send_response(302)
        self.send_header("Location", fallback)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _file(self, path, allowed=None):
        p = Path(path)
        if not path or not p.is_file():
            raise ApiError("Not found", 404)
        if allowed is not None:
            real = p.resolve()
            if not any(real.is_relative_to(Path(r).resolve()) for r in allowed if Path(r).exists()):
                raise ApiError("Not found", 404)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        self._bytes(p.read_bytes(), ctype)

    def _static(self, path):
        rel = urllib.parse.unquote(path).lstrip("/") or "index.html"
        target = (self.ui_root / rel).resolve()
        if not target.is_relative_to(self.ui_root.resolve()) or not target.is_file():
            target = self.ui_root / "index.html"  # single-page app
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "text/javascript"
        self._bytes(target.read_bytes(), ctype)


def serve(port, ui_root, mode="session"):
    Handler.ui_root = Path(ui_root)
    Handler.mode = mode
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    print(f"lumend {__version__} ({mode}) on http://127.0.0.1:{port}/", flush=True)
    httpd.serve_forever()
