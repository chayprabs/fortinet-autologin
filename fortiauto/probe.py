"""Work out whether we are online, stuck behind the FortiGate portal, or offline.

We request a URL that answers "204 No Content" on a free connection (same trick
Android and Chrome use). When the FortiGate wants a login it intercepts plain
HTTP and either redirects to, or returns a page that JavaScript-redirects to,
https://<gateway>:1000/fgtauth?<magic>. Only that exact pattern counts as
"captive", so on any other network this tool never acts.
"""

import re

from . import net

ONLINE = "online"
CAPTIVE = "captive"
OFFLINE = "offline"

FGTAUTH = re.compile(r"""https?://[^\s"'<>]+/fgtauth\?[^\s"'<>]*""")


def classify(status, location, body):
    """Return (state, portal_url) for one probe response."""
    for text in (location or "", body or ""):
        m = FGTAUTH.search(text)
        if m:
            return CAPTIVE, m.group(0).replace("&amp;", "&")
    return (ONLINE if status == 204 else OFFLINE), None


def check(url, timeout):
    """Probe once. Never raises: network trouble is reported as OFFLINE."""
    try:
        r = net.probe_get(url, timeout)
    except OSError:
        return OFFLINE, None
    return classify(r.status, r.location, r.body)
