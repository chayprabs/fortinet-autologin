# Troubleshooting

Start with:

```
python -m fortiauto status     # is it running, last login, next reset, last error
python -m fortiauto check      # what the network looks like right now
```

and read the log (path printed by `status`; `%APPDATA%\fortiauto\fortiauto.log`
on Windows, `~/.config/fortiauto/fortiauto.log` elsewhere).

Run these from the install folder (`%LOCALAPPDATA%\fortiauto\app` on Windows,
`~/.local/share/fortiauto/app` on Linux/macOS) or from a clone of the repo.

## `check` says `offline` while the portal page shows in a browser

Your portal isn't intercepting the probe URL. Open the portal in a browser,
copy any plain `http://` address that gets redirected to `.../fgtauth?...`,
and set it as `probe_url` in config.json (`python -m fortiauto config`).

## "refusing to send credentials to 'xyz'"

Your gateway uses a hostname or public IP. If you're sure it's your
college's FortiGate, add it to config.json:

```json
{ "allowed_hosts": ["auth.mycollege.edu"] }
```

## "gateway rejected the username or password"

Re-save them: `python -m fortiauto set-credentials`. The daemon waits 60 s
between attempts, so it won't lock your account in the meantime.

## "page has no FortiGate login form"

Some setups show a disclaimer page ("Accept / Decline") before the login form.
That isn't supported. Open an issue with the page's HTML (remove anything
personal) and it can be added.

## The reset isn't at 4 hours for me

Set `session_seconds` in config.json to your portal's timeout. It only
controls when the fast-polling window happens; the re-login works either way.

## I get kicked out after a few minutes of no use

That's the idle timeout. Keepalives (on by default, every 300 s) should
prevent it. If not, lower `keepalive_interval`, e.g. to 60.

## Uninstall

- Windows: `powershell -ExecutionPolicy Bypass -File scripts\uninstall-windows.ps1 -Purge`
- Linux/macOS: `sh scripts/install-unix.sh uninstall`, then `rm -r ~/.config/fortiauto`
