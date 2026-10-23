"""Append-only log with one-file rotation.

A few lines instead of the logging package keeps the resident process smaller,
and we only need "timestamp level message" anyway.
"""

import os
import sys
import time

MAX_BYTES = 256 * 1024  # then rotate to .1; at most ~512 KB on disk

_path = None
debug_enabled = False


def setup(path, debug=False):
    global _path, debug_enabled
    _path, debug_enabled = path, debug


def _write(level, msg):
    line = "%s %-5s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), level, msg)
    if sys.stderr is not None:  # None under pythonw (no console)
        try:
            sys.stderr.write(line)
        except (OSError, ValueError):
            pass
    if _path:
        try:
            if os.path.getsize(_path) > MAX_BYTES:
                os.replace(_path, _path + ".1")
        except OSError:
            pass
        try:
            with open(_path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


def debug(msg):
    if debug_enabled:
        _write("DEBUG", msg)


def info(msg):
    _write("INFO", msg)


def warn(msg):
    _write("WARN", msg)


def error(msg):
    _write("ERROR", msg)
