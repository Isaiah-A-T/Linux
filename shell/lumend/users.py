"""PS5-style sign-in: the user list and the greetd conversation."""

import hashlib
import json
import os
import pwd
import socket
import struct
import threading

from .util import ApiError, mock_enabled

AVATAR_DIRS = ["/var/lib/AccountsService/icons", "/usr/share/lumen/avatars"]
_COLORS = ["#3ee6a0", "#4da3ff", "#ff6b8b", "#ffb547", "#b48cff", "#36d6e7", "#ff8f5a"]


def color_for(name):
    return _COLORS[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(_COLORS)]


def avatar_for(user):
    for d in AVATAR_DIRS:
        path = os.path.join(d, user)
        if os.access(path, os.R_OK):
            return f"/api/avatar/{user}"
    return None


def avatar_path(user):
    for d in AVATAR_DIRS:
        path = os.path.join(d, user)
        if os.path.basename(path) == user and os.access(path, os.R_OK):
            return path
    return None


def list_users():
    if mock_enabled():
        return [
            {"username": "fenta", "name": "Fenta", "color": "#3ee6a0", "avatar": None},
            {"username": "alex", "name": "Alex", "color": "#4da3ff", "avatar": None},
            {"username": "sam", "name": "Sam", "color": "#ff6b8b", "avatar": None},
        ]
    users = []
    for p in pwd.getpwall():
        if not 1000 <= p.pw_uid < 60000 or p.pw_shell.endswith(("nologin", "false")):
            continue
        name = (p.pw_gecos.split(",")[0] or p.pw_name).strip()
        users.append({"username": p.pw_name, "name": name, "color": color_for(p.pw_name),
                      "avatar": avatar_for(p.pw_name)})
    return sorted(users, key=lambda u: u["name"].lower())


def me():
    if mock_enabled():
        return list_users()[0]
    user = pwd.getpwuid(os.getuid())
    name = (user.pw_gecos.split(",")[0] or user.pw_name).strip()
    return {"username": user.pw_name, "name": name, "color": color_for(user.pw_name),
            "avatar": avatar_for(user.pw_name)}


class Greetd:
    """Minimal client for greetd's IPC (length-prefixed JSON on a socket)."""

    def __init__(self, path=None):
        self.path = path or os.environ.get("GREETD_SOCK")
        if not self.path:
            raise ApiError("Not running under greetd.", 500)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)

    def request(self, msg):
        body = json.dumps(msg).encode()
        self.sock.sendall(struct.pack("=I", len(body)) + body)
        size = struct.unpack("=I", self._read(4))[0]
        return json.loads(self._read(size))

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ApiError("greetd closed the connection.", 500)
            buf += chunk
        return buf

    def close(self):
        self.sock.close()


_login_lock = threading.Lock()


def login(username, secret, command=("lumen-session",)):
    """Authenticate through greetd and start the console session.

    The secret (password or PIN) is answered to every secret prompt PAM
    sends. Visible prompts get the username. On failure the half-open greetd
    session is cancelled so the next try starts clean.
    """
    if mock_enabled():
        if secret == "wrong":
            raise ApiError("That password isn't right.", 401)
        return {"ok": True}
    with _login_lock:
        g = Greetd()
        try:
            resp = g.request({"type": "create_session", "username": username})
            while resp.get("type") == "auth_message":
                kind = resp.get("auth_message_type")
                answer = secret if kind == "secret" else username if kind == "visible" else None
                resp = g.request({"type": "post_auth_message_response", "response": answer})
            if resp.get("type") != "success":
                g.request({"type": "cancel_session"})
                raise ApiError("That password isn't right.", 401)
            resp = g.request({"type": "start_session", "cmd": list(command), "env": []})
            if resp.get("type") != "success":
                raise ApiError(resp.get("description") or "Couldn't start the session.", 500)
        finally:
            g.close()
    return {"ok": True}
