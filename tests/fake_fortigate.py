"""A pretend FortiGate captive portal on 127.0.0.1 for tests and local demos.

It behaves like the real thing from the client's side: plain HTTP probes get
redirected to /fgtauth?<magic> until you POST the right credentials to "/",
then the probe answers 204 and /keepalive?<token> works. `expire()` simulates
the hard timeout kicking you out.

Demo:  python -m tests.fake_fortigate   (user: student, password: hunter2)
"""

import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

LOGIN_PAGE = """<!DOCTYPE html><html><head><title>Firewall Authentication</title></head><body>
<form action="/" method="post">
<input type="hidden" name="4Tredir" value="http://www.gstatic.com/generate_204">
<input type="hidden" name="magic" value="{magic}">
{error}
<input name="username" type="text"><input name="password" type="password">
<input type="submit" value="Continue"></form></body></html>"""

SUCCESS_PAGE = ('<html><body><script language="JavaScript">'
                'window.location="{base}/keepalive?{token}";</script></body></html>')

INTERCEPT_PAGE = ('<html><body><script language="JavaScript">'
                  'window.location="{base}/fgtauth?{magic}";</script></body></html>')


class FakeFortiGate:
    def __init__(self, username="student", password="hunter2", js_intercept=False):
        self.username, self.password = username, password
        self.js_intercept = js_intercept  # intercept with a JS page instead of a 303
        self.authed = False
        self.magic = secrets.token_hex(8)
        self.token = None
        self.logins = 0
        self.keepalives = 0
        self.failed_logins = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.base = "http://127.0.0.1:%d" % self.server.server_port
        self.probe_url = self.base + "/generate_204"

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def expire(self):
        """The hard timeout: session gone, new magic."""
        self.authed = False
        self.token = None
        self.magic = secrets.token_hex(8)

    def _handler(self):
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, body="", headers=None):
                data = body.encode()
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                u = urlsplit(self.path)
                if u.path == "/fgtauth":
                    self._send(200, LOGIN_PAGE.format(magic=u.query, error=""))
                elif u.path == "/keepalive":
                    ok = gw.authed and u.query == gw.token
                    gw.keepalives += ok
                    self._send(200 if ok else 403, "keepalive")
                elif gw.authed:
                    self._send(204)
                elif gw.js_intercept:
                    self._send(200, INTERCEPT_PAGE.format(base=gw.base, magic=gw.magic))
                else:
                    self._send(303, headers={"Location": "%s/fgtauth?%s" % (gw.base, gw.magic)})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
                if (form.get("magic") == gw.magic and form.get("username") == gw.username
                        and form.get("password") == gw.password and "4Tredir" in form):
                    gw.authed = True
                    gw.logins += 1
                    gw.token = secrets.token_hex(8)
                    self._send(200, SUCCESS_PAGE.format(base=gw.base, token=gw.token))
                else:
                    gw.failed_logins += 1
                    gw.magic = secrets.token_hex(8)
                    err = "<h2>Firewall authentication failed. Please try again.</h2>"
                    self._send(200, LOGIN_PAGE.format(magic=gw.magic, error=err))

        return Handler


if __name__ == "__main__":
    gw = FakeFortiGate().start()
    print("fake FortiGate on %s  (probe_url: %s)" % (gw.base, gw.probe_url))
    print('try: set FORTIAUTO_HOME to a temp dir, put {"probe_url": "%s"} in config.json' % gw.probe_url)
    threading.Event().wait()
