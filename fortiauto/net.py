"""HTTP for the portal: GET/POST over http.client with HTTPS and redirects.

Only the short-lived login worker uses this; the resident watcher's probe is
in probe.py and needs none of it. It never honours system proxy settings:
captive-portal traffic must go straight to the gateway. Nothing global is
touched, so other apps are unaffected.
"""

from urllib.parse import urljoin, urlsplit

USER_AGENT = "fortiauto/1.1.0"
MAX_BODY = 64 * 1024  # portal pages are small; never buffer more than this


class Response:
    __slots__ = ("status", "url", "location", "body")

    def __init__(self, status, url, location, body):
        self.status = status
        self.url = url
        self.location = location
        self.body = body


def _ssl_context(verify):
    import ssl

    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _request(url, data, timeout, verify_tls):
    import http.client

    u = urlsplit(url)
    if u.scheme == "https":
        conn = http.client.HTTPSConnection(
            u.hostname, u.port or 443, timeout=timeout, context=_ssl_context(verify_tls)
        )
    elif u.scheme == "http":
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    else:
        raise OSError("unsupported URL: %s" % url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    headers = {"User-Agent": USER_AGENT, "Connection": "close", "Cache-Control": "no-cache"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        conn.request("GET" if data is None else "POST", path, body=data, headers=headers)
        r = conn.getresponse()
        body = r.read(MAX_BODY).decode("utf-8", "replace")
        return Response(r.status, url, r.getheader("Location"), body)
    except http.client.HTTPException as e:  # normalise so callers only catch OSError
        raise OSError("%s: %s" % (type(e).__name__, e)) from e
    finally:
        conn.close()


def fetch(url, data=None, timeout=5.0, verify_tls=True, follow=0):
    """GET (or POST form bytes) and return a Response. Network errors raise OSError.

    follow: how many redirects to chase (FortiGate often bounces :1000 -> :1003).
    """
    r = _request(url, data, timeout, verify_tls)
    while follow > 0 and r.status in (301, 302, 303, 307, 308) and r.location:
        follow -= 1
        if r.status in (301, 302, 303):
            data = None  # browsers turn these into a GET
        r = _request(urljoin(r.url, r.location), data, timeout, verify_tls)
    return r
