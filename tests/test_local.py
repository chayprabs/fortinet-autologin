"""Config, credentials, state and lock: the bits that touch the local disk."""

import json
import os
import tempfile
import unittest
from unittest import mock

from fortiauto import config, creds, lock
from fortiauto.state import State


class LocalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"FORTIAUTO_HOME": self.tmp.name}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        os.environ.pop("FORTIAUTO_USERNAME", None)
        os.environ.pop("FORTIAUTO_PASSWORD", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_defaults_without_config_file(self):
        cfg = config.load()
        self.assertEqual(cfg.session_seconds, 14400)
        self.assertEqual(config.app_dir(), self.tmp.name)

    def test_config_overrides_and_rejects_typos(self):
        path = config.config_path()
        with open(path, "w") as f:
            json.dump({"check_interval": 1, "allowed_hosts": ["gw.college.edu"]}, f)
        cfg = config.load()
        self.assertEqual((cfg.check_interval, cfg.allowed_hosts), (1, ["gw.college.edu"]))
        with open(path, "w") as f:
            json.dump({"check_intervall": 1}, f)
        with self.assertRaises(ValueError):
            config.load()

    def test_env_credentials_win(self):
        with mock.patch.dict(os.environ, {"FORTIAUTO_USERNAME": "a", "FORTIAUTO_PASSWORD": "b"}):
            self.assertEqual(creds.load(), ("a", "b"))

    def test_file_backend_round_trip(self):
        self.assertIsNone(creds._file_read())
        creds._file_write("student", "pässwörd")
        self.assertEqual(creds._file_read(), ("student", "pässwörd"))
        if os.name != "nt":
            self.assertEqual(os.stat(creds._file()).st_mode & 0o777, 0o600)
        self.assertTrue(creds._file_delete())
        self.assertFalse(creds._file_delete())

    @unittest.skipUnless(os.name == "nt", "Windows Credential Manager only")
    def test_windows_credential_manager_round_trip(self):
        with mock.patch.object(creds, "TARGET", "fortiauto-selftest"):
            try:
                creds._win_write("student", "pässwörd")
                self.assertEqual(creds._win_read(), ("student", "pässwörd"))
            finally:
                creds._win_delete()
            self.assertIsNone(creds._win_read())

    def test_state_persists_and_skips_redundant_writes(self):
        path = os.path.join(self.tmp.name, "state.json")
        s = State(path)
        s.update(logins=1)
        self.assertEqual(State(path).get("logins"), 1)
        mtime = os.stat(path).st_mtime_ns
        s.update(logins=1)
        self.assertEqual(os.stat(path).st_mtime_ns, mtime)

    def test_state_round_trips_types_and_odd_strings(self):
        path = os.path.join(self.tmp.name, "state.txt")
        State(path).update(logins=3, expires_at=1761300000.25, keepalive_url=None,
                           last_error="bad\tthing\nhappened", last_state="online")
        s = State(path)
        self.assertEqual(s.get("logins"), 3)
        self.assertEqual(s.get("expires_at"), 1761300000.25)
        self.assertIsNone(s.get("keepalive_url"))
        self.assertEqual(s.get("last_error"), "bad thing happened")
        self.assertEqual(s.get("last_state"), "online")

    def test_launcher_runs_isolated(self):
        import subprocess
        import sys

        import fortiauto

        launch = os.path.join(os.path.dirname(fortiauto.__file__), "launch.py")
        out = subprocess.run([sys.executable, "-I", "-S", launch, "version"],
                             capture_output=True, text=True, cwd=self.tmp.name)
        self.assertEqual(out.stdout.strip(), fortiauto.__version__)

    def test_lock_allows_one_instance(self):
        path = os.path.join(self.tmp.name, "x.lock")
        first = lock.acquire(path)
        self.assertIsNotNone(first)
        self.assertIsNone(lock.acquire(path))
        self.assertTrue(lock.is_held(path))
        first.close()
        self.assertFalse(lock.is_held(path))


if __name__ == "__main__":
    unittest.main()
