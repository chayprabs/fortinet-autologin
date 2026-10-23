# FAQ

### How do I know my Wi-Fi uses a FortiGate portal?

When you connect, the login page's address looks like
`https://10.x.x.x:1003/fgtauth?0123abcd` (or port `1000`). If you see
`fgtauth` in the URL, this tool is for you. You can also run
`python -m fortiauto check` while the login page is showing: it prints
`captive -> https://.../fgtauth?...`.

### Will it slow down my laptop or eat battery?

No. It sends one ~200-byte HTTP request every 2 seconds, uses about 17 MB of
RAM (mostly the Python interpreter itself), runs at below-normal priority,
and only writes to disk when something happens (a login, an error). There's
no browser and no polling of anything else.

### Does it change any settings on my computer?

No. It doesn't touch proxies, DNS, routes, the firewall, browsers or the
registry. It adds exactly one per-user startup entry (a Task Scheduler task
on Windows, a systemd user service on Linux, a launchd agent on macOS),
one folder with the program, and one folder with your config/log. The
uninstaller removes all of it.

### What happens at home or on other Wi-Fi?

Nothing. It only acts when the network answers with the FortiGate `fgtauth`
login page. Everywhere else it just sees "online" or "offline" and waits.

### How fast does it log back in?

Usually within about a second of being kicked. It knows when the 4-hour
session started, so it checks every 0.5 s around the expected reset. At
other times it checks every 2 s, so an unexpected logout is fixed within
about 2-3 s.

### Will my downloads / SSH / Zoom survive the reset?

The FortiGate drops your session at the timeout no matter what, so
connections open at that exact moment may still break. fortiauto makes the
gap about a second instead of "until you notice". Apps that reconnect (most
downloads managers, Zoom, `mosh`, `autossh`) will carry on.

### Can it keep me logged in past 4 hours without a re-login?

No, and it doesn't try. The hard timeout is enforced by your college's
gateway. fortiauto just does the re-login for you, instantly. Keepalives
only prevent the *idle* timeout, which is what the portal's own browser tab
is meant to do.

### Is my password safe?

On Windows it lives in Windows Credential Manager. On Linux/macOS it's a file
only you can read. It's only sent to a private-IP gateway (or a host you
allow-list). See [SECURITY.md](../SECURITY.md).

### I changed my password.

Run `python -m fortiauto set-credentials` again. No restart needed.

### My portal's timeout isn't 4 hours.

Put `{"session_seconds": 7200}` (or whatever yours is) in config.json via
`python -m fortiauto config`. Re-login works either way; this only tunes
when it checks fastest.

### How do I update?

Download the new release (or `git pull`) and run the installer again. It
replaces the old copy and restarts the background task. Your saved login and
config are kept.

### Is this allowed?

It does exactly what you'd do by hand in the browser, with your own account.
Check your institution's acceptable-use policy if you're unsure.

### Does it work on Linux / macOS?

Yes. `sh scripts/install-unix.sh` sets up a systemd user service (Linux) or
a launchd agent (macOS). CI tests every release on Windows, Linux and macOS.
