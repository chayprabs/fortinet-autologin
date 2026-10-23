"""Command line. Hand-rolled dispatch (no argparse) to keep the daemon lean."""

import os
import sys
import time

from . import __version__, config

USAGE = """fortiauto %s - stay logged in to a FortiGate captive portal

usage: fortiauto <command>

  run                watch the connection and log in automatically
                     (this is what the autostart task runs)
  status             last login, countdown to the next reset, errors
  check              probe once: online / captive / offline
  login              log in right now if the portal is asking
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


def _duration(seconds):
    seconds = int(abs(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return "%dh %02dm" % (h, m) if h else "%dm %02ds" % (m, s)


def _when(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def cmd_status():
    from . import lock, state

    p = _paths()
    st = state.State(p["state"])
    now = time.time()
    print("daemon:      %s" % ("running" if lock.is_held(p["lock"]) else "NOT running"))
    print("network:     %s" % st.get("last_state", "unknown"))
    logged_in, expires = st.get("logged_in_at"), st.get("expires_at")
    if logged_in:
        print("last login:  %s (%s ago)" % (_when(logged_in), _duration(now - logged_in)))
    if expires:
        if expires > now:
            print("next reset:  %s (in %s) - will re-login automatically"
                  % (_when(expires), _duration(expires - now)))
        else:
            print("next reset:  was due %s ago" % _duration(now - expires))
    print("logins:      %d" % st.get("logins", 0))
    if st.get("last_error"):
        print("last error:  %s" % st["last_error"])
    print("log file:    %s" % p["log"])
    return 0


def cmd_check():
    from . import probe

    cfg = config.load()
    status, portal_url = probe.check(cfg.probe_url, cfg.timeout)
    print(status + (" -> %s" % portal_url if portal_url else ""))
    return 0 if status == probe.ONLINE else 1


def cmd_login():
    from . import creds, portal, probe

    cfg = config.load()
    status, portal_url = probe.check(cfg.probe_url, cfg.timeout)
    if status != probe.CAPTIVE:
        print("no FortiGate login page right now (network: %s)" % status)
        return 0 if status == probe.ONLINE else 1
    c = creds.load()
    if not c:
        print("no credentials saved; run: fortiauto set-credentials", file=sys.stderr)
        return 1
    try:
        keepalive = portal.login(portal_url, c[0], c[1], verify_tls=cfg.verify_tls,
                                 timeout=cfg.timeout, allowed_hosts=cfg.allowed_hosts)
    except (OSError, portal.PortalError) as e:
        print("login failed: %s" % e, file=sys.stderr)
        return 1
    print("logged in" + (" (keepalive: %s)" % keepalive if keepalive else ""))
    return 0


COMMANDS = {
    "run": cmd_run,
    "status": cmd_status,
    "check": cmd_check,
    "login": cmd_login,
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
