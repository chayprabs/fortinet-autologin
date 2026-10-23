"""Where the portal username/password live.

Lookup order:
1. FORTIAUTO_USERNAME / FORTIAUTO_PASSWORD environment variables
2. Windows: Windows Credential Manager (encrypted by Windows, per user)
   Linux/macOS: credentials.json in the app folder, readable only by you (0600)

No third-party packages: the Windows store is reached through ctypes.
"""

import json
import os

from . import config

TARGET = "fortiauto"  # Credential Manager entry name


def _file():
    return os.path.join(config.app_dir(), "credentials.json")


def _file_read():
    try:
        with open(_file(), encoding="utf-8") as f:
            d = json.load(f)
        return d["username"], d["password"]
    except (OSError, ValueError, KeyError):
        return None


def _file_write(username, password):
    path = _file()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"username": username, "password": password}, f)
    os.chmod(path, 0o600)  # in case the file already existed with wider perms


def _file_delete():
    try:
        os.remove(_file())
        return True
    except FileNotFoundError:
        return False


def load():
    """Return (username, password) or None if nothing is saved."""
    u, p = os.environ.get("FORTIAUTO_USERNAME"), os.environ.get("FORTIAUTO_PASSWORD")
    if u and p:
        return u, p
    return _file_read()


def save(username, password):
    """Store credentials; returns a human description of where."""
    _file_write(username, password)
    return _file()


def clear():
    return _file_delete()
