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
  set-credentials    save your portal username/password (prompted, hidden)
  clear-credentials  delete them
  config             create/show config.json (optional; defaults work)
""" % __version__


def _paths():
    d = config.app_dir()
    return {
        "log": os.path.join(d, "fortiauto.log"),
        "state": os.path.join(d, "state.txt"),
        "lock": os.path.join(d, "fortiauto.lock"),
    }


def cmd_run(args):
    from . import daemon, lock, log, state, worker

    cfg = config.load()
    p = _paths()
    held = lock.acquire_waiting(p["lock"])
    if held is None:
        print("fortiauto is already running.")
        return 1
    log.setup(p["log"], cfg.debug)
    log.info("fortiauto %s started (checking every %ss)" % (__version__, cfg.check_interval))
    d = daemon.Daemon(cfg, state.State(p["state"]))
    import gc

    gc.freeze()  # start-up objects are permanent; the GC never touches their pages again
    ticks = 0
    try:
        while True:
            try:
                wait = d.tick()
            except Exception as e:  # never die: a bad page must not stop the watcher
                log.error("unexpected error: %r" % e)
                wait = cfg.check_interval
            ticks += 1
            if ticks % 300 == 3:  # once settled, then about every 10 minutes
                worker.trim()  # hand idle pages back to Windows (no-op elsewhere)
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


def cmd_status(args):
    from . import lock, state

    p = _paths()
    st = state.State(p["state"])
    now = time.time()
    print("fortiauto:   %s" % __version__)
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


def cmd_check(args):
    from . import probe

    cfg = config.load()
    status, portal_url = probe.check(cfg.probe_url, cfg.timeout)
    print(status + (" -> %s" % portal_url if portal_url else ""))
    return 0 if status == probe.ONLINE else 1


def cmd_login(args):
    from . import probe

    cfg = config.load()
    status, portal_url = probe.check(cfg.probe_url, cfg.timeout)
    if status != probe.CAPTIVE:
        print("no FortiGate login page right now (network: %s)" % status)
        return 0 if status == probe.ONLINE else 1
    code = cmd_worker_login([portal_url])
    print("logged in" if code == 0 else "login failed", file=sys.stderr)
    return code


def _worker_args(args):
    """Strip the trim flag; returns (args, trim_parent_when_done)."""
    from . import worker

    return [a for a in args if a != worker.TRIM_FLAG], worker.TRIM_FLAG in args


def cmd_worker_login(args):
    """Hidden: what the watcher runs in a child process."""
    from . import creds, log, portal, worker

    args, trim = _worker_args(args)
    cfg = config.load()
    log.setup(_paths()["log"], cfg.debug)
    try:
        c = creds.load()
        if not c:
            print("no credentials saved; run: fortiauto set-credentials", file=sys.stderr)
            return worker.EXIT_NOCREDS
        try:
            keepalive = portal.login(args[0], c[0], c[1], verify_tls=cfg.verify_tls,
                                     timeout=cfg.timeout, allowed_hosts=cfg.allowed_hosts)
        except portal.AuthFailed as e:
            print(e, file=sys.stderr)
            return worker.EXIT_AUTH
        except (OSError, portal.PortalError) as e:
            print(e, file=sys.stderr)
            log.warn("login worker: %s" % e)
            return worker.EXIT_ERROR
        with open(worker.result_path(), "w", encoding="utf-8") as f:
            f.write(keepalive or "")
        print(keepalive or "")
        return worker.EXIT_OK
    finally:
        if trim:
            worker.trim_parent()


def cmd_worker_keepalive(args):
    """Hidden: one keepalive hit in a child process."""
    from . import log, portal, worker

    args, trim = _worker_args(args)
    cfg = config.load()
    log.setup(_paths()["log"], cfg.debug)
    try:
        return 0 if portal.keepalive(args[0], verify_tls=cfg.verify_tls, timeout=cfg.timeout) else 1
    except OSError as e:
        log.debug("keepalive failed: %s" % e)
        return 1
    finally:
        if trim:
            worker.trim_parent()


def cmd_worker_trim(args):
    """Hidden: trim the parent's working set and exit."""
    from . import worker

    worker.trim_parent()
    return 0


def cmd_set_credentials(args):
    import getpass

    from . import creds

    username = input("Portal username: ").strip()
    password = getpass.getpass("Portal password (not shown): ")
    if not username or not password:
        print("nothing saved", file=sys.stderr)
        return 1
    where = creds.save(username, password)
    print("saved to %s" % where)
    print("the running daemon picks this up on its next login; no restart needed")
    return 0


def cmd_clear_credentials(args):
    from . import creds

    print("removed" if creds.clear() else "nothing was saved")
    return 0


def cmd_config(args):
    import json

    path = config.config_path()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config.DEFAULTS, f, indent=2)
        print("wrote defaults to %s" % path)
    else:
        print(path)
    print("edit it, then restart the daemon (or just log out and back in)")
    return 0


COMMANDS = {
    "config": cmd_config,
    "run": cmd_run,
    "status": cmd_status,
    "check": cmd_check,
    "login": cmd_login,
    "set-credentials": cmd_set_credentials,
    "clear-credentials": cmd_clear_credentials,
    "_login": cmd_worker_login,
    "_keepalive": cmd_worker_keepalive,
    "_trim": cmd_worker_trim,
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
    return fn(argv[1:]) or 0
