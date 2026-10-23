"""Settings. Everything has a sane default; config.json is optional."""

import json
import os
from types import SimpleNamespace

DEFAULTS = {
    # Answers 204 when the internet is reachable; FortiGate intercepts it otherwise.
    "probe_url": "http://www.gstatic.com/generate_204",
    # Seconds between checks. One tiny HTTP request each time.
    "check_interval": 2.0,
    # Faster checks around the moment the session is expected to expire.
    "fast_interval": 0.5,
    # Start fast checks this many seconds before the expected reset (and keep
    # them up for a minute after it).
    "fast_window": 15,
    # Your portal's hard timeout. FortiGate default for many campuses: 14400 s.
    "session_seconds": 14400,
    # Seconds between keepalive hits while online (0 disables). Stops idle timeouts.
    "keepalive_interval": 300,
    # Network timeout for every request, seconds.
    "timeout": 3.0,
    # FortiGate portals usually use a self-signed certificate, so this is off.
    # The private-IP check in portal.check_host is what protects your password.
    "verify_tls": False,
    # Extra gateway hostnames/IPs allowed to receive your credentials. Empty
    # means "private IP addresses only".
    "allowed_hosts": [],
    # Log every probe, not just changes.
    "debug": False,
}


def app_dir():
    """Per-user folder for config, state and log. Created on first use.

    FORTIAUTO_HOME overrides it (used by tests, handy for portable setups).
    """
    path = os.environ.get("FORTIAUTO_HOME")
    if path:
        os.makedirs(path, exist_ok=True)
        return path
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = os.path.join(base, "fortiauto")
    os.makedirs(path, exist_ok=True)
    return path


def config_path():
    return os.path.join(app_dir(), "config.json")


def load(path=None):
    cfg = dict(DEFAULTS)
    path = path or config_path()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        unknown = sorted(set(user) - set(DEFAULTS))
        if unknown:
            raise ValueError("unknown keys in %s: %s" % (path, ", ".join(unknown)))
        cfg.update(user)
    return SimpleNamespace(**cfg)
