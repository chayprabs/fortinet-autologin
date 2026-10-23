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


def _win():
    import ctypes
    from ctypes import wintypes

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    pcred = ctypes.POINTER(CREDENTIAL)
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(pcred)]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredWriteW.argtypes = [pcred, wintypes.DWORD]
    adv.CredWriteW.restype = wintypes.BOOL
    adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    adv.CredDeleteW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    adv.CredFree.restype = None
    return ctypes, CREDENTIAL, adv


_GENERIC, _PERSIST_LOCAL_MACHINE = 1, 2


def _win_read():
    ctypes, CREDENTIAL, adv = _win()
    p = ctypes.POINTER(CREDENTIAL)()
    if not adv.CredReadW(TARGET, _GENERIC, 0, ctypes.byref(p)):
        return None
    try:
        c = p.contents
        password = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-16-le")
        return c.UserName, password
    finally:
        adv.CredFree(p)


def _win_write(username, password):
    ctypes, CREDENTIAL, adv = _win()
    blob = password.encode("utf-16-le")
    buf = ctypes.create_string_buffer(blob, len(blob))
    c = CREDENTIAL()
    c.Type = _GENERIC
    c.TargetName = TARGET
    c.UserName = username
    c.Persist = _PERSIST_LOCAL_MACHINE
    c.CredentialBlobSize = len(blob)
    c.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
    if not adv.CredWriteW(ctypes.byref(c), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def _win_delete():
    _, _, adv = _win()
    return bool(adv.CredDeleteW(TARGET, _GENERIC, 0))


def load():
    """Return (username, password) or None if nothing is saved."""
    u, p = os.environ.get("FORTIAUTO_USERNAME"), os.environ.get("FORTIAUTO_PASSWORD")
    if u and p:
        return u, p
    return _win_read() if os.name == "nt" else _file_read()


def save(username, password):
    """Store credentials; returns a human description of where."""
    if os.name == "nt":
        _win_write(username, password)
        return "Windows Credential Manager (entry %r)" % TARGET
    _file_write(username, password)
    return _file()


def clear():
    return _win_delete() if os.name == "nt" else _file_delete()
