"""The watch loop: probe, and log in the moment the portal shows up."""

import time

from . import creds, log, portal, probe
from .probe import CAPTIVE, ONLINE


def _clock_time(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


class Daemon:
    """One `tick()` = one probe plus whatever it calls for. Returns seconds to sleep.

    Collaborators are injectable so tests can run it without a network.
    """

    def __init__(self, cfg, state, check=probe.check, login=portal.login,
                 keepalive=portal.keepalive, get_creds=creds.load, clock=time.time):
        self.cfg = cfg
        self.state = state
        self.check = check
        self.login = login
        self.keepalive = keepalive
        self.get_creds = get_creds
        self.clock = clock
        self.last = None
        self.retry_at = 0.0
        self.failures = 0
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
            self._keepalive(now)
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
            ok = self.keepalive(url, verify_tls=cfg.verify_tls, timeout=cfg.timeout)
            log.debug("keepalive %s" % ("ok" if ok else "not accepted"))
        except OSError as e:
            log.debug("keepalive failed: %s" % e)

    def _login(self, portal_url, now):
        cfg = self.cfg
        if now < self.retry_at:
            return
        # Read every time so `fortiauto set-credentials` works without a restart.
        c = self.get_creds()
        if not c:
            log.warn("portal is asking for a login but no credentials are saved; "
                     "run: fortiauto set-credentials")
            self.retry_at = now + 30
            return
        t0 = self.clock()
        try:
            keepalive_url = self.login(portal_url, c[0], c[1], verify_tls=cfg.verify_tls,
                                       timeout=cfg.timeout, allowed_hosts=cfg.allowed_hosts)
        except portal.AuthFailed as e:
            # Back off hard: hammering a wrong password can lock the account.
            log.error("%s; retrying in 60s (fix with: fortiauto set-credentials)" % e)
            self.state.update(last_error=str(e))
            self.retry_at = now + 60
            return
        except (OSError, portal.PortalError) as e:
            self.failures += 1
            wait = min(2 ** self.failures, 30)  # 2, 4, 8, 16, 30, 30...
            log.warn("login attempt failed (%s); retrying in %ds" % (e, wait))
            self.state.update(last_error=str(e))
            self.retry_at = now + wait
            return
        self.failures = 0
        self.last_keepalive = now
        # The gateway can take a moment to open up; don't re-login on the next probe.
        self.retry_at = now + 3
        expires = now + cfg.session_seconds
        self.state.update(logged_in_at=now, expires_at=expires, keepalive_url=keepalive_url,
                          logins=self.state.get("logins", 0) + 1, last_error=None)
        log.info("logged in (%.1fs); next reset expected around %s"
                 % (self.clock() - t0, _clock_time(expires)))
