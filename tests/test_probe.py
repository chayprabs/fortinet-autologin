import os
import unittest

from fortiauto import probe

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class ClassifyTest(unittest.TestCase):
    def test_204_is_online(self):
        self.assertEqual(probe.classify(204, None, ""), (probe.ONLINE, None))

    def test_redirect_to_fgtauth_is_captive(self):
        loc = "http://10.10.0.1:1000/fgtauth?0f1e2d3c4b5a6978"
        self.assertEqual(probe.classify(303, loc, ""), (probe.CAPTIVE, loc))

    def test_javascript_intercept_page_is_captive(self):
        state, url = probe.classify(200, None, fixture("intercept.html"))
        self.assertEqual(state, probe.CAPTIVE)
        self.assertEqual(url, "https://10.10.0.1:1003/fgtauth?0f1e2d3c4b5a6978")

    def test_html_entities_are_unescaped(self):
        body = '<a href="https://10.0.0.1:1003/fgtauth?abc&amp;x=1">'
        self.assertEqual(probe.classify(200, None, body)[1], "https://10.0.0.1:1003/fgtauth?abc&x=1")

    def test_other_captive_portals_are_ignored(self):
        # Some other network's portal: not ours, never act on it.
        body = '<form action="https://login.example.net/auth">'
        self.assertEqual(probe.classify(200, None, body), (probe.OFFLINE, None))
        self.assertEqual(probe.classify(302, "https://hotel.example/login", ""), (probe.OFFLINE, None))

    def test_unreachable_is_offline(self):
        # Port 1 on loopback refuses immediately.
        self.assertEqual(probe.check("http://127.0.0.1:1/generate_204", 1.0), (probe.OFFLINE, None))


if __name__ == "__main__":
    unittest.main()
