import unittest

from fortiauto import portal
from tests.test_probe import fixture


class ParseFormTest(unittest.TestCase):
    def test_fortios_login_page(self):
        action, hidden, user, pw = portal.parse_form(fixture("login.html"))
        self.assertEqual(action, "/")
        self.assertEqual(hidden, {"4Tredir": "http://www.gstatic.com/generate_204",
                                  "magic": "0f1e2d3c4b5a6978"})
        self.assertEqual((user, pw), ("username", "password"))

    def test_odd_markup(self):
        # single quotes, bare values, upper case, custom field names, no action
        html = ("<FORM method=post><INPUT type=hidden name=magic value=abc>"
                "<input type='text' name='uid'><input name=pwd type=PASSWORD></FORM>")
        self.assertEqual(portal.parse_form(html), ("/", {"magic": "abc"}, "uid", "pwd"))

    def test_not_a_login_page(self):
        for html in ("", fixture("success.html"), "<form><input name=q></form>"):
            with self.assertRaises(portal.PortalError):
                portal.parse_form(html)


class KeepaliveLinkTest(unittest.TestCase):
    def test_found_in_success_page(self):
        self.assertEqual(portal.find_keepalive(fixture("success.html"), "https://10.10.0.1:1003/"),
                         "https://10.10.0.1:1003/keepalive?0a0b0c0d0e0f1011")

    def test_relative_link(self):
        self.assertEqual(portal.find_keepalive("/keepalive?99", "https://10.0.0.1:1003/"),
                         "https://10.0.0.1:1003/keepalive?99")

    def test_missing(self):
        self.assertIsNone(portal.find_keepalive(fixture("login.html"), "https://10.0.0.1/"))
        self.assertIsNone(portal.find_keepalive(None, "https://10.0.0.1/"))


class CheckHostTest(unittest.TestCase):
    def test_private_addresses_pass(self):
        for url in ("https://10.10.0.1:1003/fgtauth?x", "http://192.168.1.1:1000/",
                    "https://172.16.5.4/", "http://127.0.0.1:8080/"):
            portal.check_host(url)

    def test_public_or_named_hosts_are_refused(self):
        for url in ("https://8.8.8.8/fgtauth?x", "https://evil.example/fgtauth?x"):
            with self.assertRaises(portal.PortalError):
                portal.check_host(url)

    def test_allow_list(self):
        portal.check_host("https://Auth.College.edu:1003/", ["auth.college.edu"])
        with self.assertRaises(portal.PortalError):
            portal.check_host("https://10.0.0.1/", ["auth.college.edu"])


if __name__ == "__main__":
    unittest.main()
