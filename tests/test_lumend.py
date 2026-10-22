import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())

from lumend import jobs, recents, store, system, update  # noqa: E402
from lumend.launchers import gog, steam, vdf  # noqa: E402


class VdfTest(unittest.TestCase):
    def test_nested_and_escapes(self):
        text = '''
        // comment
        "libraryfolders"
        {
            "0" { "path" "/home/p/.local/share/Steam" "apps" { "620" "123" } }
            "1" { "path" "/mnt/games/Steam\\\\Lib" }
        }'''
        data = vdf.loads(text)["libraryfolders"]
        self.assertEqual(data["0"]["apps"]["620"], "123")
        self.assertEqual(data["1"]["path"], "/mnt/games/Steam\\Lib")


class SteamTest(unittest.TestCase):
    def test_installed_games_skips_tools_and_reads_progress(self):
        with tempfile.TemporaryDirectory() as d:
            apps = Path(d) / "steamapps"
            apps.mkdir()
            (apps / "appmanifest_620.acf").write_text(
                '"AppState" { "appid" "620" "name" "Portal 2" "StateFlags" "4" "LastPlayed" "100" }')
            (apps / "appmanifest_1493710.acf").write_text(
                '"AppState" { "appid" "1493710" "name" "Proton Experimental" "StateFlags" "4" }')
            (apps / "appmanifest_570.acf").write_text(
                '"AppState" { "appid" "570" "name" "Dota 2" "StateFlags" "1026" '
                '"BytesToDownload" "200" "BytesDownloaded" "50" }')
            games = steam.installed_games(Path(d))
        self.assertEqual(set(games), {"620", "570"})
        self.assertTrue(games["620"]["installed"])
        self.assertEqual(games["620"]["last_played"], 100)
        self.assertFalse(games["570"]["installed"])
        self.assertEqual(games["570"]["progress"], 25.0)


class GogTest(unittest.TestCase):
    def test_extract_code(self):
        url = "https://embed.gog.com/on_login_success?origin=client&code=abc123"
        self.assertEqual(gog.extract_code(url), "abc123")
        self.assertEqual(gog.extract_code("  xyz "), "xyz")

    def test_primary_task(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "goggame-42.info").write_text(json.dumps({"playTasks": [
                {"type": "URLTask", "link": "x"},
                {"type": "FileTask", "path": "bin\\Game.exe", "isPrimary": True},
            ]}))
            self.assertEqual(gog.primary_task(d, "42")["path"], "bin\\Game.exe")


class WifiTest(unittest.TestCase):
    def test_parse_wifi_list_dedupes_and_unescapes(self):
        out = "\n".join([
            " :Cafe\\:Guest:40:WPA2",
            "*:Home:70:WPA2",
            " :Home:90:WPA2",
            " ::80:WPA2",
            " :Open Net:55:",
        ])
        nets = system.parse_wifi_list(out)
        self.assertEqual([n["ssid"] for n in nets], ["Home", "Open Net", "Cafe:Guest"])
        self.assertTrue(nets[0]["connected"])
        self.assertFalse(nets[1]["secure"])

    def test_parse_volume(self):
        self.assertEqual(system.parse_wpctl_volume("Volume: 0.45 [MUTED]"), {"volume": 45, "muted": True})


class StoreTest(unittest.TestCase):
    def test_merge_prefers_flatpak_and_records_alternative(self):
        flat = [{"source": "flatpak", "id": "org.videolan.VLC", "title": "VLC"}]
        snap = [{"source": "snap", "id": "vlc", "title": "vlc"},
                {"source": "snap", "id": "code", "title": "Visual Studio Code"}]
        merged = store.merge(flat, snap)
        self.assertEqual([c["id"] for c in merged], ["org.videolan.VLC", "code"])
        self.assertEqual(merged[0]["also"], [{"source": "snap", "id": "vlc"}])

    def test_strip_html(self):
        self.assertEqual(store.strip_html("<p>Hi &amp; bye</p><ul><li>One</li></ul>"), "Hi & bye\n• One")

    def test_install_rejects_bad_ids(self):
        with self.assertRaises(Exception):
            store.install("flatpak", "foo; rm -rf /")


class UpdateTest(unittest.TestCase):
    def test_parse_pending(self):
        text = "linux 6.17.3.arch1-1 -> 6.17.5.arch1-1\nsteam 1.0.0.83-1 -> 1.0.0.84-1 [ignored]\n:: junk\n"
        pending = update.parse_pending(text)
        self.assertEqual([p["name"] for p in pending], ["linux", "steam"])
        self.assertEqual(pending[0]["new"], "6.17.5.arch1-1")
        self.assertTrue(pending[1]["ignored"])

    def test_pacman_progress_counts_install_lines_only(self):
        self.assertEqual(update.parse_pacman_progress("(10/40) upgrading mesa"), 0.25)
        self.assertEqual(update.parse_pacman_progress("( 3/12) installing lumen"), 0.25)
        self.assertIsNone(update.parse_pacman_progress("(10/40) checking keys in keyring"))
        self.assertIsNone(update.parse_pacman_progress(":: Starting full system upgrade..."))

    def test_last_upgrade_reads_the_latest_entry(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("[2026-10-01T10:00:00+0000] [PACMAN] starting full system upgrade\n"
                    "[2026-10-01T10:05:00+0000] [ALPM] upgraded mesa (1 -> 2)\n"
                    "[2026-10-20T08:30:00+0000] [PACMAN] starting full system upgrade\n")
        try:
            self.assertEqual(update.last_upgrade(f.name), 1792485000.0)
        finally:
            os.unlink(f.name)
        self.assertIsNone(update.last_upgrade("/nonexistent/pacman.log"))

    def test_steps_run_in_order_and_failures_do_not_stop_later_steps(self):
        steps = [
            ("one", ["sh", "-c", "echo '(1/2) upgrading a'; echo '(2/2) upgrading b'"], 3, update.parse_pacman_progress),
            ("two", ["sh", "-c", "echo 50%; exit 3"], 1, jobs.percent),
            ("three", ["true"], 1, None),
        ]
        seen = {}
        job = jobs.start_steps("t", steps, on_done=lambda j: seen.update(state=j["state"]))
        for _ in range(100):
            current = next(j for j in jobs.all_jobs() if j["id"] == job["id"])
            if current["state"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(current["state"], "failed")
        self.assertEqual(current["codes"], [0, 3, 0])
        self.assertEqual(current["message"], "two failed")
        self.assertEqual(current["progress"], 100.0)
        self.assertEqual(seen["state"], "running")  # the hook runs before the job finishes


class RecentsTest(unittest.TestCase):
    def test_home_is_capped_at_15_and_ordered(self):
        now = time.time()
        items = [{"id": f"steam:{i}", "title": str(i), "installed": True, "last_played": now - i}
                 for i in range(30)]
        with mock.patch.object(recents, "load", return_value=[{"id": "steam:29", "last_played": now + 5}]):
            home = recents.home_items(items)
        self.assertEqual(len(home), recents.HOME_LIMIT)
        self.assertEqual(home[0]["id"], "steam:29")
        self.assertEqual(home[1]["id"], "steam:0")

    def test_uninstalled_items_stay_off_home(self):
        items = [{"id": "a", "installed": False, "last_played": 10}, {"id": "b", "installed": True, "last_played": 5}]
        with mock.patch.object(recents, "load", return_value=[{"id": "a", "last_played": 20}]):
            self.assertEqual([i["id"] for i in recents.home_items(items)], ["b"])


class GreetdTest(unittest.TestCase):
    """Run users.login against a fake greetd speaking the real wire format."""

    def _serve(self, script):
        import socket
        import struct
        import threading
        path = os.path.join(tempfile.mkdtemp(), "greetd.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(1)
        seen = []

        def run():
            conn, _ = srv.accept()
            for reply in script:
                size = struct.unpack("=I", conn.recv(4))[0]
                seen.append(json.loads(conn.recv(size)))
                body = json.dumps(reply).encode()
                conn.sendall(struct.pack("=I", len(body)) + body)
            conn.close()

        threading.Thread(target=run, daemon=True).start()
        return path, seen

    def test_password_login_starts_session(self):
        from lumend import users
        path, seen = self._serve([
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
            {"type": "success"},
            {"type": "success"},
        ])
        with mock.patch.dict(os.environ, {"GREETD_SOCK": path, "LUMEN_MOCK": "0"}):
            self.assertEqual(users.login("fenta", "hunter2"), {"ok": True})
        self.assertEqual(seen[0], {"type": "create_session", "username": "fenta"})
        self.assertEqual(seen[1]["response"], "hunter2")
        self.assertEqual(seen[2]["cmd"], ["lumen-session"])

    def test_wrong_password_cancels(self):
        from lumend import users
        from lumend.util import ApiError
        path, seen = self._serve([
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
            {"type": "error", "error_type": "auth_error", "description": "nope"},
            {"type": "success"},
        ])
        with mock.patch.dict(os.environ, {"GREETD_SOCK": path, "LUMEN_MOCK": "0"}):
            with self.assertRaises(ApiError):
                users.login("fenta", "bad")
        self.assertEqual(seen[-1], {"type": "cancel_session"})


if __name__ == "__main__":
    unittest.main()
