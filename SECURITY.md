# Security policy

fortiauto handles your portal password, so security reports are welcome and
taken seriously.

## Reporting a vulnerability

Please **don't open a public issue**. Use GitHub's private
[security advisory form](https://github.com/chayprabs/fortinet-autologin/security/advisories/new).
You'll get a reply within a few days.

## How credentials are handled

- **Windows:** stored in Windows Credential Manager (encrypted by Windows,
  scoped to your user account). Never written to disk by fortiauto.
- **Linux/macOS:** `~/.config/fortiauto/credentials.json`, created with
  permissions `0600` (readable only by you).
- **Environment variables** `FORTIAUTO_USERNAME` / `FORTIAUTO_PASSWORD` take
  priority if set.
- Credentials are only ever sent to a gateway on a private, loopback or CGNAT
  IP address, or a host you list in `allowed_hosts`. A fake portal on some
  other network can't collect them.
- They never appear in logs, the state file, command-line arguments or URLs.
  The login worker reads them itself; they aren't passed on its command line.

## Known trade-off

FortiGate captive portals usually use a self-signed certificate, so TLS
verification is off by default (`verify_tls: false`), just like clicking
through the browser warning. Someone who can impersonate the gateway's
private IP on your local network could therefore see the login. If your
college's portal has a valid certificate, set `"verify_tls": true`.
