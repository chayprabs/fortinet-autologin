"""One running daemon per user. The OS drops the lock if the process dies."""

import os


def acquire(path):
    """Return an open file holding the lock, or None if another instance has it."""
    f = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def is_held(path):
    f = acquire(path)
    if f is None:
        return True
    f.close()
    return False
