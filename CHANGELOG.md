# Changelog

## 1.0.0 - 2026-10-24

First release.

- Detects the FortiGate captive portal (redirect or JavaScript intercept) and
  logs in automatically, usually within a second of being kicked out.
- Tracks the expected hard-timeout reset (default 14400 s) and probes faster
  around it; `fortiauto status` shows a countdown.
- Sends portal keepalives while online to avoid idle timeouts.
- Credentials in Windows Credential Manager, a 0600 file, or env vars;
  only sent to private-IP gateways unless allow-listed.
- Tiny resident watcher (raw-socket probe); logins run in a short-lived worker.
- Per-user autostart for Windows (Task Scheduler), Linux (systemd --user) and
  macOS (launchd). No admin, no pip, no dependencies.
