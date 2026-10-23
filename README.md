# fortinet-autologin

[![ci](https://github.com/chayprabs/fortinet-autologin/actions/workflows/ci.yml/badge.svg)](https://github.com/chayprabs/fortinet-autologin/actions/workflows/ci.yml)

Stay logged in to a FortiGate captive portal (college / office Wi-Fi) without
babysitting it.

FortiGate portals kick you out on a hard timer, often **14400 s (4 hours)**,
and make you log in again. Downloads die, SSH drops, overnight jobs stall.
`fortiauto` runs quietly in the background, tracks when the reset is due, and
**logs you back in within about a second** of being kicked out. No browser, no clicking.

- **Fast:** probes every 2 s, every 0.5 s around the expected reset. Measured
  re-login after a kick: about 1 s.
- **Light:** about 17 MB of RAM (most of that is Python itself), one tiny HTTP
  request every 2 s, disk writes only when something happens.
- **Zero dependencies:** Python 3.9+ standard library only. Nothing gets `pip install`ed,
  and it runs with `-S`, so your installed packages are never loaded.
- **Leaves the rest of your machine alone:** it doesn't touch proxies, DNS, routes, firewall
  or browser settings. It only acts when it sees the FortiGate login page, so on
  any other network it does nothing.
- **Keeps your password safe:** it's stored in Windows Credential Manager (or a `0600`
  file on Linux/macOS), and only sent to a private-IP gateway.
- **Fully automatic:** starts at logon, restarts itself, needs no admin/root,
  and uninstalls with one command.

## Install

You need Python 3.9 or newer ([python.org](https://www.python.org/downloads/)).

```bash
git clone https://github.com/chayprabs/fortinet-autologin
cd fortinet-autologin
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

This copies the tool to `%LOCALAPPDATA%\fortiauto\app` and adds a per-user
Task Scheduler task that runs hidden at every logon, at below-normal
priority, even on battery.

### Linux / macOS

```bash
sh scripts/install-unix.sh
```

On Linux that's a `systemd --user` service; on macOS a launchd agent.

### Save your portal login (once)

```bash
cd %LOCALAPPDATA%\fortiauto\app      # Windows
cd ~/.local/share/fortiauto/app      # Linux / macOS
python -m fortiauto set-credentials
```

You're prompted for your username and password, and the password isn't shown
as you type. The running service picks them up on its next login, with no restart needed.

## Use

There's nothing to do. To peek:

```text
$ python -m fortiauto status
daemon:      running
network:     online
last login:  2026-10-24 09:12:03 (1h 47m ago)
next reset:  2026-10-24 13:12:03 (in 2h 12m) - will re-login automatically
logins:      14
log file:    C:\Users\you\AppData\Roaming\fortiauto\fortiauto.log
```

| command | what it does |
|---|---|
| `run` | the watcher (what autostart runs) |
| `status` | running?, last login, countdown to next reset, last error |
| `check` | probe once: `online` / `captive -> <portal url>` / `offline` |
| `login` | log in right now if the portal is asking |
| `set-credentials` / `clear-credentials` | manage the saved login |
| `config` | create/show `config.json` (optional; defaults work) |

## Configure (optional)

`python -m fortiauto config` writes `config.json` with the defaults
([config.example.json](config.example.json)):

| key | default | meaning |
|---|---|---|
| `session_seconds` | `14400` | your portal's hard timeout |
| `check_interval` | `2.0` | seconds between probes |
| `fast_interval` / `fast_window` | `0.5` / `15` | faster probes from 15 s before the expected reset until 60 s after |
| `keepalive_interval` | `300` | hit the portal's keepalive URL (stops idle timeouts); `0` = off |
| `allowed_hosts` | `[]` | extra gateway hostnames allowed to receive credentials (default: private IPs only) |
| `verify_tls` | `false` | FortiGate portals usually use a self-signed cert |
| `probe_url` | gstatic `generate_204` | any plain-HTTP URL that returns 204 when you're online |

## How it works

The watcher probes `http://www.gstatic.com/generate_204` over a raw socket.
On a free connection that returns `204`; behind the portal, the FortiGate
intercepts it and points to `https://<gateway>:1000/fgtauth?<magic>`. When it
sees that, it spawns a short-lived worker that loads the form, posts
`magic` + `4Tredir` + your username/password, saves the keepalive URL and the
expected reset time, and exits. Details, safety notes and measurements:
[docs/how-it-works.md](docs/how-it-works.md).

Problems? See [docs/troubleshooting.md](docs/troubleshooting.md).

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall-windows.ps1 -Purge   # Windows
```
```bash
sh scripts/install-unix.sh uninstall && rm -r ~/.config/fortiauto               # Linux / macOS
```

## Development

```bash
python -m unittest discover -s tests -t . -v   # 38 tests, no network needed
python -m tests.fake_fortigate                  # a fake portal to play with
```

The tests include a fake FortiGate server, so the whole login → kick →
re-login cycle runs end to end on any machine.

## Notes

This automates exactly what you'd do by hand in the browser, with your own
account. Check your institution's acceptable-use policy. Similar scripts
exist (e.g. [guptarohit/Fortinet-automatic-login](https://github.com/guptarohit/Fortinet-automatic-login));
this one focuses on reacting within seconds, a small footprint, and
installing cleanly as a background service.

MIT licensed.
