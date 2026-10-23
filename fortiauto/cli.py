"""Command line. Hand-rolled dispatch (no argparse) to keep the daemon lean."""

import os
import sys
import time

from . import __version__, config

USAGE = """fortiauto %s - stay logged in to a FortiGate captive portal

usage: fortiauto <command>

  run                watch the connection and log in automatically
                     (this is what the autostart task runs)
""" % __version__


def _paths():
    d = config.app_dir()
    return {
        "log": os.path.join(d, "fortiauto.log"),
        "state": os.path.join(d, "state.json"),
        "lock": os.path.join(d, "fortiauto.lock"),
    }


def cmd_run():
    from . import daemon, lock, log, state

    cfg = config.load()
    p = _paths()
    held = lock.acquire(p["lock"])
    if held is None:
        print("fortiauto is already running.")
        return 1
    log.setup(p["log"], cfg.debug)
    log.info("fortiauto %s started (checking every %ss)" % (__version__, cfg.check_interval))
    d = daemon.Daemon(cfg, state.State(p["state"]))
    try:
        while True:
            try:
                wait = d.tick()
            except Exception as e:  # never die: a bad page must not stop the watcher
                log.error("unexpected error: %r" % e)
                wait = cfg.check_interval
            time.sleep(wait)
    except KeyboardInterrupt:
        log.info("stopped")
    finally:
        held.close()
    return 0


COMMANDS = {
    "run": cmd_run,
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "help"
    if cmd in ("help", "-h", "--help"):
        print(USAGE)
        return 0
    if cmd in ("version", "--version"):
        print(__version__)
        return 0
    fn = COMMANDS.get(cmd)
    if fn is None:
        print("unknown command: %s\n\n%s" % (cmd, USAGE), file=sys.stderr)
        return 2
    return fn() or 0
