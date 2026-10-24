"""Talk to the FortiGate captive portal: read the login form, log in, keep alive.

The FortiOS login page is a plain form posted to "/" on the gateway with hidden
fields `magic` (session token from the redirect) and `4Tredir` (where to send
you afterwards), plus the username and password inputs. On success the gateway
answers with a page that points at /keepalive?<token>.
"""

import re
from urllib.parse import urlencode, urljoin, urlsplit

from . import net
from .errors import AuthFailed, NoCredentials, PortalError  # noqa: F401 (re-exported)


_INPUT = re.compile(r"<input\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")
_FORM_ACTION = re.compile(r"""<form\b[^>]*?\baction\s*=\s*["']?([^"'\s>]*)""", re.I)
_KEEPALIVE = re.compile(r"""[^\s"'<>]*/keepalive\?[^\s"'<>]+""")


def _attrs(tag):
    out = {}
    for m in _ATTR.finditer(tag):
        dq, sq, bare = m.group(2), m.group(3), m.group(4)
        out[m.group(1).lower()] = dq if dq is not None else sq if sq is not None else bare
    return out


def parse_form(body):
    """Return (action, hidden_fields, username_field, password_field).

    Raises PortalError if the page is not a FortiGate login form.
    """
    hidden, user_field, pass_field = {}, None, None
    for tag in _INPUT.findall(body or ""):
        a = _attrs(tag)
        name = a.get("name")
        if not name:
            continue
        kind = (a.get("type") or "text").lower()
        if kind == "hidden":
            hidden[name] = a.get("value", "")
        elif kind == "password":
            pass_field = name
        elif kind in ("text", "email") and user_field is None:
            user_field = name
    if "magic" not in hidden or not pass_field:
        raise PortalError("page has no FortiGate login form")
    m = _FORM_ACTION.search(body)
    return (m.group(1) if m else "") or "/", hidden, user_field or "username", pass_field


def find_keepalive(text, base):
    """Absolute keepalive URL from a post-login page/redirect, or None."""
    m = _KEEPALIVE.search(text or "")
    return urljoin(base, m.group(0)) if m else None


def _internal(ip_text):
    import ipaddress

    ip = ipaddress.ip_address(ip_text.split("%")[0])  # drop IPv6 zone id
    return ip.is_private or ip in ipaddress.ip_network("100.64.0.0/10")


def check_host(url, allowed_hosts=()):
    """Refuse to send credentials anywhere except the campus gateway.

    Private/loopback/CGNAT addresses pass (FortiGate portals are almost always
    on 10.x / 172.16-31.x / 192.168.x / 100.64.x), and so do hostnames like
    fw.college.edu that resolve *only* to such addresses. Anything else must
    be listed in `allowed_hosts`. This stops a spoofed page on some other
    network from harvesting your password.
    """
    host = (urlsplit(url).hostname or "").lower()
    if host in [h.lower() for h in allowed_hosts]:
        return
    try:
        ok = _internal(host)
    except ValueError:  # a name, not an IP
        import socket

        try:
            addrs = {a[4][0] for a in socket.getaddrinfo(host, None)}
        except OSError:
            addrs = set()
        ok = bool(addrs) and all(_internal(a) for a in addrs)
    if not ok:
        raise PortalError(
            "refusing to send credentials to %r; if this is your gateway add it to "
            "allowed_hosts in config.json" % host
        )


def login(portal_url, username, password, verify_tls=False, timeout=5.0, allowed_hosts=()):
    """Log in through the portal. Returns the keepalive URL (may be None).

    Raises AuthFailed on wrong credentials, PortalError on an unexpected page,
    OSError on network trouble.
    """
    check_host(portal_url, allowed_hosts)
    page = net.fetch(portal_url, timeout=timeout, verify_tls=verify_tls, follow=3)
    action, fields, user_field, pass_field = parse_form(page.body)
    target = urljoin(page.url, action)
    check_host(target, allowed_hosts)
    fields[user_field] = username
    fields[pass_field] = password
    # follow=0: after login the gateway redirects to your original site, which
    # we do not need to load. The keepalive link is in this response.
    r = net.fetch(target, urlencode(fields).encode(), timeout=timeout, verify_tls=verify_tls)
    keepalive = find_keepalive(r.location, target) or find_keepalive(r.body, target)
    if keepalive:
        return keepalive
    if r.status >= 400:
        raise PortalError("gateway answered HTTP %d to the login" % r.status)
    # Anything that looks like "back to the login page" is a rejection, so the
    # daemon applies its long backoff instead of re-posting a bad password.
    text = ((r.location or "") + r.body).lower()
    try:
        parse_form(r.body)
        rejected = True
    except PortalError:
        rejected = "fgtauth" in text or "authentication failed" in text
    if rejected:
        raise AuthFailed("gateway rejected the username or password")
    return None  # no keepalive link, but no sign of failure either


def keepalive(url, verify_tls=False, timeout=5.0):
    """Hit the keepalive URL, like the portal's own browser tab does."""
    return net.fetch(url, timeout=timeout, verify_tls=verify_tls).status == 200
