"""One running daemon per user. The OS drops the lock if the process dies."""

import os
import time


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


def acquire_waiting(path, seconds=10.0, step=0.5):
    """Like acquire, but give an old copy that is still exiting (an upgrade or a
    quick restart) a few seconds to let go before deciding we're a duplicate."""
    deadline = time.time() + seconds
    while True:
        f = acquire(path)
        if f is not None or time.time() >= deadline:
            return f
        time.sleep(step)


def is_held(path):
    f = acquire(path)
    if f is None:
        return True
    f.close()
    return False
