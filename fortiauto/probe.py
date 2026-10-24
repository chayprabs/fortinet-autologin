"""Work out whether we are online, stuck behind the FortiGate portal, or offline.

We request a URL that answers "204 No Content" on a free connection (same trick
Android and Chrome use). When the FortiGate wants a login it intercepts plain
HTTP and either redirects to, or returns a page that JavaScript-redirects to,
https://<gateway>:1000/fgtauth?<magic>. Only that exact pattern counts as
"captive", so on any other network this tool never acts.

This runs every couple of seconds in the resident watcher, so it uses only the
built-in `_socket` module and plain string search: no socket.py/enum, re or
urllib (together several MB of RAM).
"""

import _socket

ONLINE = "online"
CAPTIVE = "captive"
OFFLINE = "offline"

MAX_BODY = 64 * 1024  # never buffer more than this
_STOP = frozenset(" \t\r\n\"'<>")
_REQUEST = "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: fortiauto\r\nCache-Control: no-cache\r\n\r\n"


def find_fgtauth(text):
    """The first http(s)://.../fgtauth?... URL in text, or None."""
    i = text.find("/fgtauth?")
    while i >= 0:
        start = max(text.rfind("http://", 0, i), text.rfind("https://", 0, i))
        if start >= 0 and not any(c in _STOP for c in text[start:i]):
            end, n = i, len(text)
            while end < n and text[end] not in _STOP:
                end += 1
            return text[start:end].replace("&amp;", "&")
        i = text.find("/fgtauth?", i + 1)
    return None


def classify(status, location, body):
    """Return (state, portal_url) for one probe response."""
    for text in (location or "", body or ""):
        url = find_fgtauth(text)
        if url:
            return CAPTIVE, url
    return (ONLINE if status == 204 else OFFLINE), None


def split_http(url):
    """'http://host[:port]/path' -> (host, port, path). Only plain HTTP is probed."""
    if not url.startswith("http://"):
        raise ValueError("probe_url must be plain http:// (portals only intercept HTTP)")
    hostport, _, path = url[7:].partition("/")
    host, _, port = hostport.partition(":")
    return host, int(port or 80), "/" + path


def _complete(data):
    """True once a whole response is buffered, so keep-alive servers can't stall us."""
    head, sep, body = data.partition(b"\r\n\r\n")
    if not sep:
        return False
    first, _, rest = head.partition(b"\r\n")
    if first.split()[1:2] == [b"204"]:
        return True
    for line in rest.split(b"\r\n"):
        if line[:15].lower() == b"content-length:":
            n = line[15:].strip()
            return n.isdigit() and len(body) >= int(n)
    return False


def http_get(url, timeout):
    """Minimal HTTP/1.0 GET -> (status, location, body). Raises OSError/ValueError."""
    host, port, path = split_http(url)
    req = (_REQUEST % (path, host if port == 80 else "%s:%d" % (host, port))).encode("ascii")
    data, err = b"", None
    for family, kind, proto, _, addr in _socket.getaddrinfo(host, port, 0, _socket.SOCK_STREAM):
        s = _socket.socket(family, kind, proto)
        try:
            s.settimeout(timeout)
            s.connect(addr)
            s.sendall(req)
            try:
                while len(data) < MAX_BODY and not _complete(data):
                    b = s.recv(8192)
                    if not b:
                        break
                    data += b
            except OSError:
                if not data:  # a server that sent something and then stalled still counts
                    raise
            break
        except OSError as e:
            err = e  # try the next address (e.g. IPv6 then IPv4)
        finally:
            s.close()
    else:
        raise err or OSError("no address for %s" % host)
    head, _, body = data.decode("utf-8", "replace").partition("\r\n\r\n")
    lines = head.split("\r\n")
    parts = lines[0].split(" ", 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/") or not parts[1].isdigit():
        raise OSError("not an HTTP response")
    location = None
    for line in lines[1:]:
        if line[:9].lower() == "location:":
            location = line[9:].strip()
    return int(parts[1]), location, body


def check(url, timeout):
    """Probe once. Never raises: network trouble is reported as OFFLINE."""
    try:
        status, location, body = http_get(url, timeout)
    except (OSError, ValueError):
        return OFFLINE, None
    return classify(status, location, body)
