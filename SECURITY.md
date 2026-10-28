# Security policy

Tunnelbox holds VPN credentials and opens a way into other people's networks, so security
reports are taken seriously and handled before anything else.

## Supported versions

| Version | Supported |
|---|---|
| 3.x — the latest release | Yes — fixes ship as a new 3.x release |
| 2.x and older (FortiVPN 2) | No, install the latest 3.x instead |

Fixes are not backported: only the newest release is supported. The panel's own update
check tells you when a new one is out, and the registry image
`ghcr.io/mysttic/tunnelbox:latest` always points at the newest release. FortiVPN 2 does not
update itself to Tunnelbox: install Tunnelbox from scratch and import an export of your
connections (README, "Coming from FortiVPN 2").

## Reporting a vulnerability

**Please do not open a public issue for a vulnerability.** Report it privately through
GitHub's private vulnerability reporting instead: the repository's **Security** tab →
**Report a vulnerability**, or directly
<https://github.com/Mysttic/tunnelbox/security/advisories/new>. Only the maintainer sees
the report.

A useful report contains:

- the Tunnelbox version (shown next to the title in the panel header, also on the
  master-password screen) and how it was installed — ZIP package, registry image or from
  source;
- the operating system and the Docker Desktop or Docker Engine version;
- the steps to reproduce and what an attacker gains.

Never include real VPN credentials, a real `vault.enc` or exported configuration, or data
from a client network — made-up values are enough to show the problem.

Tunnelbox is maintained by one person, so expect a first reply within about a week. Once the
issue is confirmed, we agree on a fix and a disclosure date; the fix ships as a new release
and the advisory is published with it, crediting you unless you prefer otherwise.

## Threat model

### What Tunnelbox protects

- **Only this computer can reach it.** Docker publishes the panel (`127.0.0.1:25263`) and
  the forwarded ports (`127.0.0.2`–`127.0.0.60`, ports 13391–13449) on the `127.0.0.0/8`
  loopback of the computer only. Nothing listens on a network interface, so other devices
  on your LAN or Wi-Fi cannot reach the panel, nor the machines behind your VPNs through
  it. Changing the `ports:` lines of `docker-compose.yml` to another address removes this
  protection.
- **Saved credentials are encrypted at rest.** Profiles live in `data/vault.enc`. The key
  is derived from the master password with **scrypt** (N = 2^14, r = 8, p = 1, a random
  16-byte salt per vault, a 32-byte key) and the content is encrypted with **AES-256-GCM**
  under a fresh random 12-byte nonce on every write. The master password itself is never
  stored — not on disk and not in the browser. The derived key stays only in the panel's
  memory while the vault is unlocked; locking the panel or restarting the container drops
  it. An exported configuration file is the same encrypted vault. A forgotten master
  password cannot be recovered.
- **The API needs a session after unlocking.** Unlocking (or creating, or importing) the
  vault returns a random per-session token; every other API call must carry it in the
  `X-Auth` header and is refused without it. There is one session at a time — a new unlock
  replaces the token, and locking the panel invalidates it. The browser keeps the token in
  the tab's session storage, never in a cookie. A handful of endpoints work before
  unlocking: the vault status, creating and unlocking a vault, downloading the
  still-encrypted vault file and importing a configuration file together with that file's
  own password.
- **Only this computer's names are accepted.** The panel answers requests addressed to
  `127.0.0.1`, `localhost` or a `*.localhost` name (such as `tunnelbox.localhost`) and
  refuses any other `Host` header with HTTP 400. Listening on the loopback alone would not
  be enough: a web page can point its own domain at `127.0.0.1` (DNS rebinding) and then
  call the API as if it were the panel — for example to download the encrypted vault
  through the endpoints above. The browser still sends that page's domain in `Host`, so
  the request is refused.
- **No traffic you did not ask for.** Apart from your VPN tunnels, the only outbound
  connection the panel makes by itself is the update check — at most once a day, to
  `api.github.com`, asking for the list of releases behind the project page (the
  `Mysttic/Mysttic` repository). It sends no user data (GitHub sees your IP address, as
  with any web request). Turn it off in **⚙ Settings → Check for updates**, and the panel
  connects to nothing but your VPNs. Downloads happen only when you start them: the
  **Update** button on Windows fetches the release package from GitHub, and only from that
  repository's release downloads (the file size is checked before unpacking);
  `docker compose pull` fetches the registry image.

### What you should know

- **The container runs privileged.** The panel creates network namespaces, veth pairs,
  NAT rules and IPsec policies at runtime, sets sysctls on interfaces it has just created
  and opens `/dev/ppp` for pppd — the README explains in detail
  [why the container is privileged](README.md#why-the-container-is-privileged). Treat it
  like any root-level local tool: whoever controls the container has root on the Docker
  host (the Docker Desktop virtual machine on Windows and macOS, the computer itself on
  Linux). Install it only from the
  [project page](https://mysttic.github.io/Mysttic/tunnelbox/) or from the images this
  repository's workflow publishes (`ghcr.io/mysttic/tunnelbox`, `mysttic/tunnelbox` on
  Docker Hub).
- **Locking the panel protects the configuration, not active tunnels.** VPN connections
  keep running while the panel is locked, and so do their forwarded ports. Disconnect
  first if you want the way in closed.
- **A new gateway certificate is trusted on first use.** The "Trust the certificate and
  connect" button remembers that certificate's fingerprint for the profile. If a gateway
  you have used before suddenly presents an unknown certificate, check with the network's
  administrator before trusting it.

### Out of scope

- **Malware, or other users, on the same computer** who can run Docker commands, or who
  can reach `127.0.0.1` while the vault is unlocked or tunnels are up. Tunnelbox cannot
  defend against something that already has that level of access to your computer.
- **The VPN servers themselves** — FortiGate gateways, IPsec peers and the client networks
  behind them, including their configuration and certificates.
- **Bugs in openfortivpn, strongSwan, pppd, socat or the Debian base** are best reported
  to those projects. Do tell us if a release ships a version with a known vulnerability —
  [THIRD_PARTY.md](THIRD_PARTY.md) explains how to see exactly which versions a release
  contains.

In scope, for example: anything that lets a web page you visit, another device on your
network, or a crafted configuration file read or change the vault, call the API without
unlocking it, run commands in the container, or reach a forwarded port from outside this
computer.
