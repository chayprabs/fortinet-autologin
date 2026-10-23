"""Talk to the FortiGate captive portal: read the login form, log in, keep alive.

The FortiOS login page is a plain form posted to "/" on the gateway with hidden
fields `magic` (session token from the redirect) and `4Tredir` (where to send
you afterwards), plus the username and password inputs. On success the gateway
answers with a page that points at /keepalive?<token>.
"""

import re


class PortalError(Exception):
    """The portal did not behave like a FortiGate login portal."""


class AuthFailed(PortalError):
    """The gateway rejected the username/password."""


_INPUT = re.compile(r"<input\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")
_FORM_ACTION = re.compile(r"""<form\b[^>]*?\baction\s*=\s*["']?([^"'\s>]*)""", re.I)


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
