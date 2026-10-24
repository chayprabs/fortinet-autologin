"""Exceptions shared by the watcher and the login worker (no imports, on purpose)."""


class PortalError(Exception):
    """The portal did not behave like a FortiGate login portal."""


class AuthFailed(PortalError):
    """The gateway rejected the username/password."""


class NoCredentials(PortalError):
    """Nothing saved yet: run `fortiauto set-credentials`."""
