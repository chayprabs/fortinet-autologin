"""The watch loop: probe, and log in the moment the portal shows up."""

import time

from . import log, portal, probe, worker
from .probe import CAPTIVE, ONLINE


def _clock_time(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


class Daemon:
    """One `tick()` = one probe plus whatever it calls for. Returns seconds to sleep.

    login(portal_url) -> keepalive_url and keepalive(url) -> bool default to the
    out-of-process worker; tests inject in-process or fake versions.
    """

    def __init__(self, cfg, state, check=probe.check, login=None, keepalive=None,
                 clock=time.time):
        self.cfg = cfg
        self.state = state
        self.check = check
        self.login = login or (lambda url: worker.login(url, cfg))
        self.keepalive = keepalive or (lambda url: worker.keepalive(url, cfg))
        self.clock = clock
        self.last = None
        self.retry_at = 0.0
        self.attempts = 0  # login attempts since we last saw ONLINE
        self.last_keepalive = 0.0

    def tick(self):
        cfg = self.cfg
        status, portal_url = self.check(cfg.probe_url, cfg.timeout)
        now = self.clock()
        if status != self.last:
            log.info("network: %s" % status)
            self.last = status
            self.state.update(last_state=status)
        else:
            log.debug("network: %s" % status)
        if status == CAPTIVE:
            self._login(portal_url, now)
        elif status == ONLINE:
            self.attempts = 0  # only real internet access proves a login worked
            self._keepalive(now)
        return self.interval(self.clock())

    def interval(self, now):
        """Normal pace, or fast pace in the window around the expected reset."""
        cfg = self.cfg
        expires = self.state.get("expires_at")
        if expires and expires - cfg.fast_window <= now <= expires + 60:
            return cfg.fast_interval
        return cfg.check_interval

    def _keepalive(self, now):
        cfg = self.cfg
        url = self.state.get("keepalive_url")
        if not url or cfg.keepalive_interval <= 0:
            return
        if now - self.last_keepalive < cfg.keepalive_interval:
            return
        self.last_keepalive = now
        try:
            ok = self.keepalive(url)
            log.debug("keepalive %s" % ("ok" if ok else "not accepted"))
        except OSError as e:
            log.debug("keepalive failed: %s" % e)

    def _login(self, portal_url, now):
        cfg = self.cfg
        if now < self.retry_at:
            return
        # Every attempt, even one that "succeeds", pushes the next one out
        # (2, 4, 8, 16, 30 s) until the internet actually works. A portal
        # that silently ignores us can never be hammered.
        self.attempts += 1
        wait = min(2 ** self.attempts, 30)
        self.retry_at = now + wait
        t0 = self.clock()
        try:
            # Credentials are read on every login, so `fortiauto set-credentials`
            # takes effect without a restart.
            keepalive_url = self.login(portal_url)
        except portal.NoCredentials:
            log.warn("portal is asking for a login but no credentials are saved; "
                     "run: fortiauto set-credentials")
            self.retry_at = now + 30
            return
        except portal.AuthFailed as e:
            # Back off hard: hammering a wrong password can lock the account.
            log.error("%s; retrying in 60s (fix with: fortiauto set-credentials)" % e)
            self.state.update(last_error=str(e))
            self.retry_at = now + 60
            return
        except (OSError, portal.PortalError) as e:
            log.warn("login attempt failed (%s); retrying in %ds" % (e, wait))
            self.state.update(last_error=str(e))
            return
        self.last_keepalive = now
        expires = now + cfg.session_seconds
        self.state.update(logged_in_at=now, expires_at=expires, keepalive_url=keepalive_url,
                          logins=self.state.get("logins", 0) + 1, last_error=None)
        log.info("logged in (%.1fs); next reset expected around %s"
                 % (self.clock() - t0, _clock_time(expires)))
