# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-10-24

### Fixed
- Upgrading could leave the watcher stopped: the new copy started while the
  old one was still exiting, saw its lock, and quit as a "duplicate". The
  watcher now waits up to 10 s for an exiting copy, and the Windows installer
  makes sure the old process is gone before starting the new one.

## [1.1.0] - 2026-10-24

### Changed
- **The background watcher uses about 85% less RAM: a ~2.4 MB working set,
  down from ~16.4 MB** (private memory down from ~9.7 MB to ~7.4 MB), measured
  on Windows 11 with Python 3.14. How:
  - The probe uses the built-in `_socket` and plain string search: no `socket`,
    `re` or `urllib` in the watcher.
  - The login worker is started with `os.spawnv` instead of `subprocess` and
    reports back through its exit code, a result file and the log.
  - The state file is plain `key<TAB>value` text (`state.txt`) instead of JSON,
    and `json` is only imported when a `config.json` exists.
  - The background task starts `fortiauto/launch.py` with `-I -S` instead of
    `-m`, which avoids `runpy`.
  - `gc.freeze()` after start-up, and on Windows the worker trims the watcher's
    idle pages after each run (and about every 10 minutes).
- The login and re-login behaviour is unchanged.

### Upgrade
Run the new `install.cmd`. Your saved login and config are kept.

## [1.0.2] - 2026-10-24

### Added
- `fortiauto status` shows the installed version.
- README: verified on a real campus (BITS Pilani, re-login in 0.9 s).

### Removed
- `config.example.json`. It duplicated the built-in defaults; run
  `fortiauto config` to get an up-to-date file, or see the table in the README.

The login logic is unchanged from 1.0.1.

## [1.0.1] - 2026-10-24

### Fixed
- Portals reached by **hostname** (e.g. `https://fw.bits-pilani.ac.in:8090/fgtauth`)
  were refused by the credential safety check. A hostname is now accepted when
  it resolves only to private addresses, which is just as safe as a private IP.
  Reported from BITS Pilani.

### Added
- End-to-end test with a gateway reached by hostname on a non-standard port.

## [1.0.0] - 2026-10-24

First release.

### Added
- Detects the FortiGate captive portal (HTTP redirect or JavaScript intercept
  to `/fgtauth?<magic>`) and logs in automatically, usually within about a
  second of being kicked out.
- Tracks the expected hard-timeout reset (default 14400 s) and checks every
  0.5 s around it; `fortiauto status` shows a countdown.
- Portal keepalives while online, to prevent idle-timeout logouts.
- Credentials in Windows Credential Manager, a `0600` file (Linux/macOS), or
  environment variables. They're re-read on every login, so changes need no restart.
- Credentials are only sent to private/loopback/CGNAT gateways or allow-listed hosts.
- Tiny resident watcher (raw-socket probe); HTTPS logins run in a
  short-lived, isolated worker process. About 17 MB RAM measured on Windows.
- Backoff: retries at 2 → 4 → 8 → 16 → 30 s until the internet actually
  works; a rejected password waits 60 s between tries.
- Per-user autostart with no admin and no pip: Windows Task Scheduler
  (`install.cmd`), Linux `systemd --user`, macOS launchd. The installers offer
  to save your login, and each has a one-step uninstall.
- Commands: `run`, `status`, `check`, `login`, `set-credentials`,
  `clear-credentials`, `config`.
- 41 tests including a fake FortiGate server; CI on Windows, Linux and macOS
  with Python 3.9 and 3.13.
- Docs: README, how it works, FAQ, troubleshooting, security policy,
  contributing guide, issue and PR templates.

[1.1.1]: https://github.com/chayprabs/fortinet-autologin/releases/tag/v1.1.1
[1.1.0]: https://github.com/chayprabs/fortinet-autologin/releases/tag/v1.1.0
[1.0.2]: https://github.com/chayprabs/fortinet-autologin/releases/tag/v1.0.2
[1.0.1]: https://github.com/chayprabs/fortinet-autologin/releases/tag/v1.0.1
[1.0.0]: https://github.com/chayprabs/fortinet-autologin/releases/tag/v1.0.0
