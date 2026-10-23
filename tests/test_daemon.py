"""Daemon decisions with a fake clock and fake network (no sockets)."""

import os
import tempfile
import unittest
from types import SimpleNamespace

from fortiauto import config, portal
from fortiauto.daemon import Daemon
from fortiauto.probe import CAPTIVE, OFFLINE, ONLINE
from fortiauto.state import State

PORTAL = "https://10.0.0.1:1003/fgtauth?abc"


class Harness:
    def __init__(self, tmp, creds=("u", "p")):
        self.now = 1000.0
        self.net = ONLINE
        self.creds = creds
        self.login_error = None
        self.logins = []
        self.keepalives = []
        cfg = SimpleNamespace(**config.DEFAULTS)
        self.d = Daemon(cfg, State(os.path.join(tmp, "s.json")), check=self.check,
                        login=self.login, keepalive=self.keepalive, clock=lambda: self.now)

    def check(self, url, timeout):
        return (self.net, PORTAL if self.net == CAPTIVE else None)

    def login(self, url):
        if not self.creds:
            raise portal.NoCredentials("none")
        self.logins.append(self.now)
        if self.login_error:
            raise self.login_error
        self.net = ONLINE  # like the real gateway: login opens the internet
        return "https://10.0.0.1:1003/keepalive?k"

    def keepalive(self, url):
        self.keepalives.append(self.now)
        return True

    def run(self, seconds, net=None):
        """Advance the fake clock by `seconds`, ticking at the daemon's own pace."""
        if net:
            self.net = net
        end = self.now + seconds
        while self.now < end:
            self.now += self.d.tick()


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.h = Harness(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_idle_when_online_without_session(self):
        self.h.run(60)
        self.assertEqual(self.h.logins, [])
        self.assertEqual(self.h.keepalives, [])

    def test_nothing_happens_offline(self):
        self.h.run(60, net=OFFLINE)
        self.assertEqual(self.h.logins, [])

    def test_logs_in_on_first_captive_probe(self):
        self.h.net = CAPTIVE
        self.h.d.tick()
        self.assertEqual(self.h.logins, [1000.0])
        self.assertEqual(self.h.d.state.get("expires_at"), 1000.0 + 14400)

    def test_no_credentials_waits_30s(self):
        self.h.creds = None
        self.h.run(29, net=CAPTIVE)
        self.assertEqual(self.h.logins, [])
        self.h.creds = ("u", "p")
        self.h.run(3)
        self.assertEqual(len(self.h.logins), 1)

    def test_network_errors_back_off_exponentially(self):
        self.h.login_error = OSError("timed out")
        self.h.run(40, net=CAPTIVE)
        gaps = [b - a for a, b in zip(self.h.logins, self.h.logins[1:])]
        self.assertEqual(gaps[:3], [2, 4, 8])

    def test_wrong_password_waits_a_minute(self):
        self.h.login_error = portal.AuthFailed("rejected")
        self.h.run(119, net=CAPTIVE)
        self.assertEqual(len(self.h.logins), 2)  # t=0 and t=60

    def test_login_that_does_not_open_internet_backs_off(self):
        self.h.login = None
        self.h.d.login = lambda url: self.h.logins.append(self.h.now)  # "works", stays captive
        self.h.run(40, net=CAPTIVE)
        gaps = [b - a for a, b in zip(self.h.logins, self.h.logins[1:])]
        self.assertEqual(gaps[:4], [2, 4, 8, 16])

    def test_keepalive_every_interval_while_online(self):
        self.h.net = CAPTIVE
        self.h.d.tick()
        self.h.run(301 * 3, net=ONLINE)
        self.assertEqual(len(self.h.keepalives), 3)

    def test_fast_polling_around_expected_reset(self):
        self.h.net = CAPTIVE
        self.h.d.tick()
        d = self.h.d
        self.assertEqual(d.interval(1000 + 100), 2.0)
        self.assertEqual(d.interval(1000 + 14400 - 10), 0.5)
        self.assertEqual(d.interval(1000 + 14400 + 30), 0.5)
        self.assertEqual(d.interval(1000 + 14400 + 120), 2.0)

    def test_relogin_within_a_second_of_the_kick(self):
        self.h.net = CAPTIVE
        self.h.d.tick()
        self.h.run(14400 - 1, net=ONLINE)
        kick = self.h.now
        self.h.run(5, net=CAPTIVE)
        self.assertEqual(len(self.h.logins), 2)
        self.assertLessEqual(self.h.logins[1] - kick, 0.5)


if __name__ == "__main__":
    unittest.main()
