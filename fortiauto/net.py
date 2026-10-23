"""Tiny HTTP client on top of http.client.

Why not urllib.request: it imports a lot more (memory), and it honours system
proxy settings, which is wrong for captive-portal traffic that must go straight
to the gateway. This talks directly to the host and never touches any global
setting, so other apps on the machine are unaffected.
"""

import http.client
from urllib.parse import urlsplit

USER_AGENT = "fortiauto/1.0"
MAX_BODY = 64 * 1024  # portal pages are small; never buffer more than this

_contexts = {}


class Response:
    __slots__ = ("status", "url", "location", "body")

    def __init__(self, status, url, location, body):
        self.status = status
        self.url = url
        self.location = location
        self.body = body


def _ssl_context(verify):
    # ssl is imported lazily: the idle probe is plain HTTP and never needs it.
    if verify not in _contexts:
        import ssl

        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        _contexts[verify] = ctx
    return _contexts[verify]


def _request(url, data, timeout, verify_tls):
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


def fetch(url, data=None, timeout=5.0, verify_tls=True):
    """GET (or POST form bytes) and return a Response. Network errors raise OSError."""
    return _request(url, data, timeout, verify_tls)
