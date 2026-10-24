# Contributing

Thanks for helping. A few ground rules keep this tool small and safe.

## Principles

- **Standard library only.** No third-party dependencies, ever. That's what
  lets it run with `python -I -S` and keep only ~2.5 MB of RAM in use.
- **Keep the watcher's imports minimal.** `daemon.py`, `probe.py`, `state.py`,
  `log.py`, `lock.py`, `config.py` and `worker.py` must not import `re`, `json`,
  `socket`, `subprocess`, `urllib` or `ssl` at module level. Heavy work belongs
  in the worker child process.
- **Never touch anything global.** No proxy, DNS, route, firewall or browser
  changes. Per-user files and one startup entry only.
- **Only act on FortiGate.** Detection must stay specific to the `fgtauth`
  portal, so the tool stays idle on every other network.
- **Python 3.9+** syntax (no `match`, no `X | Y` type unions).

## Setup

```bash
git clone https://github.com/chayprabs/fortinet-autologin
cd fortinet-autologin
python -m unittest discover -s tests -t . -v
```

No virtualenv or install needed. `python -m tests.fake_fortigate` starts a
fake portal (user `student`, password `hunter2`) you can point the tool at
with `FORTIAUTO_HOME` and a `config.json` containing its `probe_url`.

## Adding support for a different portal page

If your college's FortiGate page isn't recognised, the most useful thing is
the page's HTML with anything personal removed. Add it under
`tests/fixtures/`, add a test in `tests/test_portal.py`, then adjust
`fortiauto/portal.py` until it passes.

## Pull requests

- One logical change per PR, with a test.
- `python -m unittest discover -s tests -t .` must pass. CI runs it on
  Windows, Linux and macOS with Python 3.9 and 3.13.
- Update `CHANGELOG.md` under an "Unreleased" heading.
