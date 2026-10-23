"""Run logins and keepalives in a short-lived child process.

The resident watcher only probes, so it stays tiny. http.client, ssl and the
Windows credential code load in the child, which exits right after (about
50-100 ms of process start per login). The child is the same Python with -S,
so installed packages can't interfere, and it never opens a window.
"""

import os
import sys

from . import portal

EXIT_OK, EXIT_ERROR, EXIT_AUTH, EXIT_NOCREDS = 0, 1, 3, 4

_PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW


def _run(args, timeout):
    import subprocess

    cmd = [sys.executable, "-S", "-m", "fortiauto"] + args
    try:
        return subprocess.run(cmd, cwd=_PKG_PARENT, capture_output=True, text=True,
                              timeout=timeout, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise OSError("worker timed out")


def login(portal_url, cfg):
    """Same contract as portal.login, but out of process."""
    r = _run(["_login", portal_url], cfg.timeout * 4 + 5)
    msg = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""
    if r.returncode == EXIT_OK:
        return r.stdout.strip() or None
    if r.returncode == EXIT_AUTH:
        raise portal.AuthFailed(msg or "gateway rejected the username or password")
    if r.returncode == EXIT_NOCREDS:
        raise portal.NoCredentials(msg or "no credentials saved")
    raise portal.PortalError(msg or "login worker exited with %d" % r.returncode)


def keepalive(url, cfg):
    return _run(["_keepalive", url], cfg.timeout + 5).returncode == EXIT_OK
