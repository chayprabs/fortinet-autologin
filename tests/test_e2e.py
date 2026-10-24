"""End to end against the fake FortiGate: real HTTP, real parsing, real daemon."""

import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from fortiauto import config, portal, probe
from fortiauto.daemon import Daemon
from fortiauto.state import State
from tests.fake_fortigate import FakeFortiGate


def make_cfg(gw, **over):
    cfg = dict(config.DEFAULTS, probe_url=gw.probe_url, timeout=2.0)
    cfg.update(over)
    return SimpleNamespace(**cfg)


class E2ETest(unittest.TestCase):
    def setUp(self):
        self.gw = FakeFortiGate().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.state = State(os.path.join(self.tmp.name, "state.json"))

    def tearDown(self):
        self.gw.stop()
        self.tmp.cleanup()

    def daemon(self, password="hunter2", **over):
        cfg = make_cfg(self.gw, **over)
        return Daemon(cfg, self.state,
                      login=lambda url: portal.login(url, "student", password, timeout=2),
                      keepalive=lambda url: portal.keepalive(url, timeout=2))

    def test_probe_sees_portal_then_login_opens_internet(self):
        status, url = probe.check(self.gw.probe_url, 2)
        self.assertEqual(status, probe.CAPTIVE)
        keepalive = portal.login(url, "student", "hunter2", timeout=2)
        self.assertTrue(keepalive.startswith(self.gw.base + "/keepalive?"))
        self.assertEqual(probe.check(self.gw.probe_url, 2), (probe.ONLINE, None))
        self.assertTrue(portal.keepalive(keepalive, timeout=2))

    def test_gateway_reached_by_hostname(self):
        # Like https://fw.bits-pilani.ac.in:8090/fgtauth: a name, odd port.
        gw = FakeFortiGate(host="localhost").start()
        try:
            status, url = probe.check(gw.probe_url, 2)
            self.assertEqual(status, probe.CAPTIVE)
            self.assertTrue(url.startswith("http://localhost:"))
            portal.login(url, "student", "hunter2", timeout=2)
            self.assertTrue(gw.authed)
        finally:
            gw.stop()

    def test_wrong_password_raises_auth_failed(self):
        _, url = probe.check(self.gw.probe_url, 2)
        with self.assertRaises(portal.AuthFailed):
            portal.login(url, "student", "nope", timeout=2)

    def test_daemon_logs_in_and_relogs_after_hard_timeout(self):
        d = self.daemon()
        d.tick()
        self.assertTrue(self.gw.authed)
        self.assertEqual(self.state.get("logins"), 1)
        self.assertAlmostEqual(self.state.get("expires_at"),
                               self.state.get("logged_in_at") + 14400, delta=1)

        self.gw.expire()  # the 14400 s kick
        d.retry_at = 0     # pretend the 3 s settle time has passed
        t0 = time.monotonic()
        d.tick()
        self.assertTrue(self.gw.authed)
        self.assertEqual(self.gw.logins, 2)
        self.assertLess(time.monotonic() - t0, 5, "re-login must take well under 5 s")

    def test_rejection_by_redirect_is_auth_failed(self):
        self.gw.fail_redirect = True
        _, url = probe.check(self.gw.probe_url, 2)
        with self.assertRaises(portal.AuthFailed):
            portal.login(url, "student", "nope", timeout=2)

    def test_daemon_handles_javascript_intercept(self):
        self.gw.js_intercept = True
        self.daemon().tick()
        self.assertTrue(self.gw.authed)

    def test_daemon_backs_off_on_wrong_password(self):
        d = self.daemon(password="wrong")
        for _ in range(5):
            d.tick()
        self.assertEqual(self.gw.failed_logins, 1, "must not hammer the gateway")
        self.assertIn("rejected", self.state.get("last_error"))

    def test_daemon_through_real_worker_process(self):
        env = {"FORTIAUTO_HOME": self.tmp.name, "FORTIAUTO_USERNAME": "student",
               "FORTIAUTO_PASSWORD": "hunter2"}
        with mock.patch.dict(os.environ, env):
            d = Daemon(make_cfg(self.gw), self.state)  # default = subprocess worker
            t0 = time.monotonic()
            d.tick()
            self.assertTrue(self.gw.authed)
            self.assertLess(time.monotonic() - t0, 5)
            self.assertTrue(self.state.get("keepalive_url").startswith(self.gw.base))
            os.environ["FORTIAUTO_PASSWORD"] = "wrong"
            self.gw.expire()
            d.retry_at = 0
            d.tick()
            self.assertIn("rejected", self.state.get("last_error"))
            del os.environ["FORTIAUTO_PASSWORD"]
            os.environ.pop("FORTIAUTO_USERNAME")
            d.retry_at = 0
            d.tick()  # no creds -> waits, no crash
            self.assertGreater(d.retry_at, time.time() + 20)

    def test_daemon_sends_keepalive(self):
        d = self.daemon(keepalive_interval=0.01)
        d.tick()
        time.sleep(0.05)
        d.tick()
        self.assertEqual(self.gw.keepalives, 1)


if __name__ == "__main__":
    unittest.main()
