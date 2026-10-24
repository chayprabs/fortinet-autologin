"""Run logins and keepalives in a short-lived child process.

The resident watcher only probes, so it stays tiny. HTTPS, the credential
store and the login logic load in the child, which exits right after (about
50-100 ms per run). The child:
- is started with os.spawnv (subprocess would drag threading into the watcher);
- runs isolated (`-I -S`), so installed packages can't interfere, and never
  opens a window (it's the same pythonw.exe as the watcher);
- writes its own detailed log lines and passes the keepalive URL back through
  a small file, so no pipes are needed;
- on Windows, finally asks Windows to trim the watcher's idle memory pages, so
  the watcher itself never has to load ctypes.
"""

import os
import sys

from . import config
from .errors import AuthFailed, NoCredentials, PortalError

EXIT_OK, EXIT_ERROR, EXIT_AUTH, EXIT_NOCREDS = 0, 1, 3, 4
TRIM_FLAG = "--trim-parent"

_LAUNCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch.py")


def result_path():
    return os.path.join(config.app_dir(), "keepalive.url")


def _quote(arg):
    # os.spawnv doesn't quote on Windows; our args never contain double quotes.
    return '"%s"' % arg if os.name == "nt" and (" " in arg or "\t" in arg) else arg


def _run(args):
    argv = [sys.executable, "-I", "-S", _LAUNCH] + list(args) + [TRIM_FLAG]
    return os.spawnv(os.P_WAIT, sys.executable, [_quote(a) for a in argv])


def login(portal_url):
    """Same contract as portal.login, but out of process."""
    path = result_path()
    try:
        os.remove(path)
    except OSError:
        pass
    code = _run(["_login", portal_url])
    if code == EXIT_OK:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip() or None
        except OSError:
            return None
    if code == EXIT_AUTH:
        raise AuthFailed("gateway rejected the username or password")
    if code == EXIT_NOCREDS:
        raise NoCredentials("no credentials saved")
    raise PortalError("login failed (exit %s, details in the log above)" % code)


def keepalive(url):
    return _run(["_keepalive", url]) == EXIT_OK


def trim():
    """Have a throwaway child trim this process's working set (Windows only)."""
    if os.name == "nt":
        _run(["_trim"])


def trim_parent():
    """Called in the child: give the parent's idle pages back to Windows.

    This only drops pages from RAM that the watcher isn't touching; they come
    back on demand. Nothing about the watcher's behaviour changes.
    """
    if os.name != "nt":
        return
    import ctypes

    k32 = ctypes.WinDLL("kernel32")
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    # PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION; same user, so always allowed.
    handle = k32.OpenProcess(0x0100 | 0x0400, False, os.getppid())
    if handle:
        k32.SetProcessWorkingSetSize(handle, ctypes.c_size_t(-1).value, ctypes.c_size_t(-1).value)
        k32.CloseHandle(handle)
