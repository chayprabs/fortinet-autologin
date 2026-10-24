# fortinet-autologin

[![ci](https://github.com/chayprabs/fortinet-autologin/actions/workflows/ci.yml/badge.svg)](https://github.com/chayprabs/fortinet-autologin/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/chayprabs/fortinet-autologin)](https://github.com/chayprabs/fortinet-autologin/releases/latest)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)

**Never get kicked off your college Wi-Fi again.** fortiauto keeps you
logged in to a FortiGate captive portal and logs you back in within about a
second whenever the session runs out.

FortiGate portals log you out on a hard timer, often **14400 seconds (4 hours)**,
and make you type your password again. Downloads die, SSH drops, overnight
training runs stall, and you only notice hours later. fortiauto runs silently
in the background, tracks when the reset is coming, and handles the re-login
for you, day and night, with no browser and no clicking.

| | |
|---|---|
| **Fast** | Re-logs in about 1 s after the kick (checks every 0.5 s around the expected reset, every 2 s otherwise) |
| **Light** | About 17 MB RAM (mostly Python itself), one tiny request every 2 s, below-normal priority |
| **Harmless** | Changes no system settings: no proxy, DNS, firewall or browser changes. Stays idle on every non-FortiGate network |
| **Safe** | Password kept in Windows Credential Manager (or a `0600` file); only sent to a gateway on your private network |
| **Zero dependencies** | Python standard library only. Nothing to `pip install` |
| **Hands-off** | Starts at logon, survives sleep/wake, needs no admin, one-click uninstall |

**Verified on a real campus:** BITS Pilani's FortiGate (`fw.bits-pilani.ac.in:8090`).
After a portal logout it detected the login page and logged back in within
**0.9 s**, and the internet was back about 3 s after the kick. Got it working on
your campus? Open an issue or PR to add it here.

---

## Contents

- [Quick start (Windows)](#quick-start-windows)
- [Quick start (Linux / macOS)](#quick-start-linux--macos)
- [Install from git](#install-from-git)
- [Check that it works](#check-that-it-works)
- [Commands](#commands)
- [Configuration](#configuration)
- [Update](#update)
- [Uninstall](#uninstall)
- [How it works](#how-it-works)
- [FAQ](#faq) · [Troubleshooting](docs/troubleshooting.md) · [Security](SECURITY.md)

---

## Quick start (Windows)

**1. Install Python** (skip if you have 3.9 or newer).
Download it from [python.org/downloads](https://www.python.org/downloads/) and
run the installer with the default options. To check, open PowerShell and
run `py --version`.

**2. Download fortiauto.**
Get **[fortinet-autologin.zip](https://github.com/chayprabs/fortinet-autologin/releases/latest/download/fortinet-autologin.zip)**
from the [latest release](https://github.com/chayprabs/fortinet-autologin/releases/latest),
then right-click it and choose **Extract All**.

**3. Double-click `install.cmd`** in the extracted folder.
It doesn't need admin rights. A window opens and:
- copies the program to `%LOCALAPPDATA%\fortiauto\app`
- registers a background task that starts hidden at every logon
- asks for your **portal username and password** once (the password isn't
  shown as you type) and saves them in Windows Credential Manager

**4. That's it.** You can delete the downloaded folder. From now on, whenever
the portal logs you out, fortiauto logs you back in.

<details>
<summary>Prefer a single PowerShell command?</summary>

```powershell
$z="$env:TEMP\fortiauto.zip"; iwr https://github.com/chayprabs/fortinet-autologin/releases/latest/download/fortinet-autologin.zip -OutFile $z; Expand-Archive $z "$env:TEMP\fortiauto" -Force; & "$env:TEMP\fortiauto\fortinet-autologin\install.cmd"
```
</details>

## Quick start (Linux / macOS)

You need `python3` 3.9 or newer, which most systems already have.

```bash
curl -L -o fortiauto.zip https://github.com/chayprabs/fortinet-autologin/releases/latest/download/fortinet-autologin.zip
unzip fortiauto.zip && cd fortinet-autologin
sh scripts/install-unix.sh
```

The script installs to `~/.local/share/fortiauto/app`, sets up a
`systemd --user` service (Linux) or a launchd agent (macOS), and asks for
your portal login. Your credentials are saved to
`~/.config/fortiauto/credentials.json` with `0600` permissions.

On Linux, run `loginctl enable-linger $(id -un)` if you want it to keep
running while you're logged out (for example, on a headless lab machine).

## Install from git

```bash
git clone https://github.com/chayprabs/fortinet-autologin
cd fortinet-autologin
# Windows: double-click install.cmd   or   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
# Linux/macOS:
sh scripts/install-unix.sh
```

Prefer pip? `pip install git+https://github.com/chayprabs/fortinet-autologin`
gives you a `fortiauto` command. In that case you set up autostart yourself
with `fortiauto run`.

## Check that it works

Open a terminal in the install folder:

```powershell
cd $env:LOCALAPPDATA\fortiauto\app      # Windows (PowerShell)
```
```bash
cd ~/.local/share/fortiauto/app         # Linux / macOS
```

then:

```text
$ python -m fortiauto status
daemon:      running
network:     online
last login:  2026-10-24 09:12:03 (1h 47m ago)
next reset:  2026-10-24 13:12:03 (in 2h 12m) - will re-login automatically
logins:      14
log file:    C:\Users\you\AppData\Roaming\fortiauto\fortiauto.log
```

On Windows, `py` works in place of `python`. While on campus, the
`python -m fortiauto check` command prints `captive -> https://…/fgtauth?…`
when the login page is up, and `online` otherwise.

## Commands

All commands are `python -m fortiauto <command>`, or `fortiauto <command>` if pip-installed.

| command | what it does |
|---|---|
| `status` | is it running, last login, countdown to the next reset, last error |
| `check` | probe once: `online` / `captive -> <portal url>` / `offline` |
| `login` | log in right now if the portal is asking |
| `set-credentials` | save or replace your portal username/password (prompted, hidden) |
| `clear-credentials` | delete the saved login |
| `config` | create/show `config.json` (optional, the defaults work) |
| `run` | the background watcher itself (what autostart runs) |

## Configuration

Optional. `python -m fortiauto config` creates `config.json` in
`%APPDATA%\fortiauto` (Windows) or `~/.config/fortiauto` (Linux/macOS)
with these defaults ([config.example.json](config.example.json)):

| key | default | meaning |
|---|---|---|
| `session_seconds` | `14400` | your portal's hard timeout (4 h) |
| `check_interval` | `2.0` | seconds between checks |
| `fast_interval` | `0.5` | seconds between checks near the expected reset |
| `fast_window` | `15` | start fast checks this many seconds before the reset (they continue 60 s after) |
| `keepalive_interval` | `300` | seconds between portal keepalives (stops *idle* logouts); `0` = off |
| `allowed_hosts` | `[]` | extra gateway hosts allowed to receive your login (private IPs, and names resolving only to them, are always allowed) |
| `verify_tls` | `false` | verify the portal's HTTPS certificate (most FortiGates use a self-signed one) |
| `probe_url` | `http://www.gstatic.com/generate_204` | any plain-HTTP URL that returns `204` when you're online |
| `debug` | `false` | log every check, not just changes |

After editing, restart the background task, or just sign out of Windows and back in.

## Update

Download the new release (or `git pull`) and run the installer again
(`install.cmd` or `sh scripts/install-unix.sh`). It replaces the program
and restarts the task. Your login and config are kept.

## Uninstall

- **Windows:** double-click `uninstall.cmd`. That removes the task, the
  program, your saved login, config and log. To keep your login and config,
  run `powershell -ExecutionPolicy Bypass -File scripts\uninstall-windows.ps1`
  without `-Purge`.
- **Linux / macOS:** `sh scripts/install-unix.sh uninstall`, then
  `rm -r ~/.config/fortiauto` to also delete your login and config.

## How it works

```
every 2 s (0.5 s near the expected reset)
GET http://www.gstatic.com/generate_204  (raw socket, ~200 bytes)
   ├─ 204 ............................ online  → portal keepalive every 5 min
   ├─ redirect/page with /fgtauth?… .. captive → short-lived worker:
   │                                              GET login form → POST magic + 4Tredir
   │                                              + username/password → save keepalive URL,
   │                                              expected reset = now + 14400 s → exit
   └─ anything else / error ........... offline or another network → do nothing
```

- The long-running watcher only probes, so it stays tiny. The HTTPS login runs
  in a separate process that exits right away.
- Failed attempts back off (2 → 4 → 8 → 16 → 30 s). A rejected password waits
  60 s between tries so your account can't get locked.
- Your credentials are re-read on every login, so changing them needs no restart.

Full details, safety notes and measurements are in [docs/how-it-works.md](docs/how-it-works.md).

## FAQ

**Is my Wi-Fi a FortiGate portal?** If the login page URL contains
`/fgtauth?`, yes.
**Does it change system settings?** No.
**Battery/RAM?** About 17 MB of RAM and negligible CPU.
**What happens at home?** Nothing; it stays idle.

More answers in [docs/faq.md](docs/faq.md). If something's wrong, see
[docs/troubleshooting.md](docs/troubleshooting.md) or
[open an issue](https://github.com/chayprabs/fortinet-autologin/issues/new/choose).

## Development

```bash
python -m unittest discover -s tests -t . -v   # 44 tests, no network or install needed
python -m tests.fake_fortigate                  # a fake FortiGate portal to play with
```

The test suite includes a fake FortiGate server, so the full login → kick →
re-login cycle is exercised end to end on Windows, Linux and macOS in CI.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Project layout

```
fortiauto/            the program (standard library only)
  probe.py            online / captive / offline detection
  portal.py           FortiGate form parsing, login, keepalive, host safety check
  daemon.py           the watch loop: timing, backoff, reset tracking
  worker.py           runs logins in a short-lived child process
  creds.py            Windows Credential Manager / 0600 file / env vars
  net.py, cli.py, config.py, state.py, log.py, lock.py
scripts/              installers for Windows, Linux (systemd), macOS (launchd)
install.cmd           double-click installer for Windows
uninstall.cmd         double-click uninstaller for Windows
tests/                unit + end-to-end tests with a fake FortiGate
docs/                 how it works, FAQ, troubleshooting
```

## Disclaimer

This automates exactly what you'd do by hand in the browser, with your own
account. Check your institution's acceptable-use policy. Not affiliated with
Fortinet. Similar scripts exist (e.g.
[guptarohit/Fortinet-automatic-login](https://github.com/guptarohit/Fortinet-automatic-login));
this one focuses on reacting within seconds, a tiny footprint, and installing
cleanly as a background service.

## License

[MIT](LICENSE) © 2026 Chaitanya Prabuddha
