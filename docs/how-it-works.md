# How it works

## The FortiGate captive portal, from the client's side

1. You join the network. The FortiGate blocks traffic until you authenticate.
2. Any plain-HTTP request you make is intercepted. The gateway answers with a
   redirect (or a tiny page with `window.location=...`) to
   `https://<gateway>:1000/fgtauth?<magic>` (or `:1003`).
3. That page is a form posted to `/` with hidden fields `magic` and `4Tredir`,
   plus `username` and `password`.
4. On success the gateway replies with a page pointing at
   `https://<gateway>:1003/keepalive?<token>`. Your browser keeps that tab open
   and reloads it to stop the *idle* timeout.
5. When the *hard* timeout (`auth-timeout`, commonly 14400 s = 4 h) runs out,
   you are back at step 2, no matter what.

## What fortiauto does

```
            every 2 s (0.5 s near the expected reset)
  ┌──────────────────────────────────────────────────────────┐
  │ GET http://www.gstatic.com/generate_204   (raw socket)   │
  └──────────────────────────────────────────────────────────┘
         │ 204                 │ fgtauth link             │ error / other
         ▼                     ▼                          ▼
      ONLINE                CAPTIVE                    OFFLINE
  keepalive every 5 min   spawn login worker         do nothing
  (in a worker)           ─ GET fgtauth page
                          ─ POST magic+4Tredir+user+pass
                          ─ remember keepalive URL
                          ─ expected reset = now + 14400 s
```

- **Only the FortiGate pattern triggers anything.** A hotel or airport portal,
  your home Wi-Fi, or no network at all: the tool stays idle.
- **The watcher is tiny.** The probe uses a raw socket, so the long-running
  process never imports `http.client`, `email` or `ssl`. Logins and keepalives
  run in a short-lived child process (`python -S -m fortiauto _login ...`)
  that exits right away.
- **Tracking the reset.** After each login it records `expires_at = now +
  session_seconds`. From 15 s before that until 60 s after, it probes every
  0.5 s, so the re-login usually lands within a second of the kick. It never
  logs you out early; it just watches closely.
- **Backoff.** Network or portal errors retry after 2, 4, 8, 16, 30 s. A
  rejected password waits 60 s between tries so it can't lock your account.
- **Credentials** are read fresh for each login (Windows Credential Manager,
  or a `0600` file on Linux/macOS, or env vars), so updating them needs no
  restart.

## Safety

- Credentials are only ever sent to a **private IP address** (10.x, 172.16-31.x,
  192.168.x, loopback) unless you add a hostname to `allowed_hosts`. A spoofed
  portal on some other network can't phish your password.
- TLS verification is off by default because FortiGate portals ship a
  self-signed certificate (your browser warns about it too). Turn on
  `verify_tls` if your college has a proper certificate.
- No system settings, proxies, DNS, routes, firewall rules or browser state
  are touched. Everything lives in one per-user folder and one startup entry.

## Footprint (measured on Windows 11, Python 3.14)

| | working set |
|---|---|
| bare `python -S` doing nothing | ~10.9 MB |
| fortiauto watcher, after logins and keepalives | ~17.5 MB |
| CPU | one ~200-byte HTTP request every 2 s |
| disk writes | only on events (login, error, state change) |

Most of that is the Python interpreter itself; the tool adds ~6 MB.
