# Tunnelbox

*🇬🇧 English · [🇵🇱 Polski](README.pl.md)*

[![Release](https://img.shields.io/github/v/release/Mysttic/tunnelbox)](https://github.com/Mysttic/tunnelbox/releases/latest)
[![CI](https://github.com/Mysttic/tunnelbox/actions/workflows/ci.yml/badge.svg)](https://github.com/Mysttic/tunnelbox/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Docker pulls](https://img.shields.io/docker/pulls/mysttic/tunnelbox)](https://hub.docker.com/r/mysttic/tunnelbox)

Tunnelbox connects you to several Fortinet (FortiGate) SSL-VPN and IPsec VPNs at once,
straight from your browser — the tunnels run inside a Docker container, so your own computer
never joins the client's network.

![Tunnelbox with several connections up at once](docs/img/en/12-kilka-polaczen.png)

```sh
curl -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml && docker compose up -d
```

Then open [http://tunnelbox.localhost:25263](http://tunnelbox.localhost:25263). On a Mac,
add the [loopback aliases](#macos-loopback-aliases) first.

Formerly FortiVPN 2. Not affiliated with or endorsed by Fortinet. Built on
[openfortivpn](https://github.com/adrienverge/openfortivpn) and
[strongSwan](https://www.strongswan.org/).

## Why not FortiClient or openfortivpn?

- **Several tunnels at once** — every connection runs in its own network namespace, so the
  networks of different clients (even with identical IP ranges) never collide. SSL-VPN and
  IPsec can be mixed freely.
- **Your own network never joins the client's** — the tunnel lives in a network namespace
  inside the container, not on your computer. Your routes, DNS and the rest of your traffic
  stay as they were; you reach the machines behind the VPN through local addresses such as
  RDP on `127.0.0.3:13392`.
- **A separate loopback address per machine** — Windows remembers RDP passwords per address,
  ignoring the port, so with one address per machine "Remember me" works for each of them
  instead of the saved passwords overwriting each other.
- **Nothing installed into your system** — no drivers, no system VPN profiles, no changes to
  your network settings. Docker is the only requirement.
- **Everything in the browser** — encrypted saved profiles, a token prompt when the gateway
  wants one, a new gateway certificate trusted with one click. The panel speaks English by
  default and Polish on request — one setting, applied to the whole interface including
  connection messages.

## Install

### 1. Docker Compose from the registry (recommended)

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, Mac) or
Docker Engine with the Compose plugin (Linux). In the folder where Tunnelbox should keep its
data, run:

```sh
curl -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml && docker compose up -d
```

and open [http://tunnelbox.localhost:25263](http://tunnelbox.localhost:25263). Windows
PowerShell 5.1 (the one built into Windows) needs `curl.exe` instead of `curl`, which is an
alias there, and the two commands run separately, because `&&` needs PowerShell 7:

```powershell
curl.exe -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml
docker compose up -d
```

- **Data** lives in `./data` next to `docker-compose.yml`.
- **Updating:** `docker compose pull`, then `docker compose up -d`, in the same folder. When
  a new version is out, the panel's update bar shows these two commands — a release appears
  only once its image is in GHCR (`ghcr.io/mysttic/tunnelbox`, the one `docker-compose.yml`
  uses); the Docker Hub copy follows it and can lag behind if copying fails.
- **Images:** `ghcr.io/mysttic/tunnelbox` (GHCR) and `mysttic/tunnelbox` (Docker Hub) for
  `linux/amd64`, `linux/arm64` and `linux/arm/v7`, tagged `latest`, `X.Y.Z` and `X.Y`. To pin
  a version, change `:latest` in `docker-compose.yml`.
- **On Windows** this path runs no `start.bat`, so fast RDP connect and the one-click update
  are not set up — the panel offers "Download .rdp file" instead (turn off ⚙ Settings →
  Fast RDP connect to get it straight away). Want both? Use the ZIP package below.

### 2. Offline ZIP package

Download `tunnelbox-X.Y.Z.zip` from the
[project page](https://mysttic.github.io/Mysttic/tunnelbox/) and unpack it into any
folder. The package carries the image (`tunnelbox-image-X.Y.Z.tar.gz`): the start script
loads it locally (`docker load`), so nothing is built and nothing is pulled from a registry.

- **Windows** — double-click `start.bat`. It also sets up fast RDP connect and the one-click
  "⬆️ Update" button in the panel. Data: `%LOCALAPPDATA%\Tunnelbox\data`.
- **Mac/Linux** — run `./start.sh`. Data: `~/.local/share/tunnelbox/data`.

The panel opens at [http://tunnelbox.localhost:25263](http://tunnelbox.localhost:25263) and
starts with Docker from then on — no terminal window to keep open. The package carries its
own short README with installation and troubleshooting notes.

### 3. From source

```sh
git clone https://github.com/Mysttic/tunnelbox.git
cd tunnelbox
./start.sh        # Windows: double-click start.bat
```

`start.bat` / `./start.sh` build the image locally (`tunnelbox:dev`, with the
`docker-compose.build.yml` override on top of `docker-compose.yml`); the first run takes a few
minutes. Data lives in `./data` in the repository.

### macOS: loopback aliases

The forwarded ports listen on `127.0.0.2`–`127.0.0.60`, and macOS routes only `127.0.0.1` to
the loopback by default: Docker Desktop for Mac needs the aliases `127.0.0.2`–`127.0.0.60` on
`lo0`, otherwise the container does not start. `./start.sh` (package and source) adds the
missing ones with `sudo`. For the registry install, add them yourself before
`docker compose up -d`:

```sh
for i in $(seq 2 60); do sudo ifconfig lo0 alias 127.0.0.$i up; done
```

The aliases disappear after a reboot, and Docker then cannot start the container on its own:
run the loop again, then `docker compose up -d` in the folder with `docker-compose.yml`
(package and source installs: just run `./start.sh`, it does both). Linux and Windows need
nothing of the kind.

### Podman and Rancher Desktop

Podman and Rancher Desktop are not tested yet — the container needs a rootful engine, because
it runs privileged with network namespaces and `/dev/ppp` (Podman: `podman machine set
--rootful`; Rancher Desktop with the dockerd (moby) engine behaves like Docker).

## Why the container is privileged

`privileged: true` is the first thing anyone reading `docker-compose.yml` asks about. It stays
because at runtime the panel:

- creates a network namespace per connection — `ip netns add` needs mount propagation on
  `/run/netns`, that is `CAP_SYS_ADMIN` and no mount denial from Docker's AppArmor profile
  `docker-default`;
- creates veth pairs, iptables NAT rules and IPsec (XFRM) policies — `CAP_NET_ADMIN`;
- writes per-interface sysctls (`rp_filter`, `forwarding`) for interfaces it has just created,
  and Docker mounts `/proc/sys` read-only unless the container is privileged;
- opens `/dev/ppp` for pppd — the device does not exist in Docker Desktop's virtual machine,
  so the entrypoint creates it with `mknod`, which the device cgroup has to allow.

A variant with `cap_add` / `devices` / `sysctls` instead is possible, but it has not been
verified with a real PPP tunnel, so 3.0.0 keeps `privileged`. It still listens only on
`127.0.0.0/8`: the panel and the forwarded ports are reachable from this computer only.

> 📖 **Full user manual with screenshots:** [docs/MANUAL.md](docs/MANUAL.md)
> (Polish: [docs/MANUAL.pl.md](docs/MANUAL.pl.md)) — step by step, from installing
> to the first RDP session. Written for people who do not work with networks.

## First steps in the panel

1. **Set a master password** — it encrypts every saved VPN profile (AES-256-GCM).
   Without it nobody can read your credentials off the disk. It cannot be recovered,
   so remember it.
2. **Add a connection** — fill in the form: connection type (SSL-VPN or IPsec), VPN
   server address, username, password, and tick "needs a token" if the client uses
   two-factor authentication. Below that, list the machines you want to reach
   (IP + remote port). The local port is assigned for you.
3. **Click "Connect"** — if the connection needs a token, the panel asks for it.
4. **Unknown certificate?** On the first connection the server usually presents a
   certificate the panel has not seen before. You get a "Trust the certificate and
   connect" button — one click and it is done. No copying hashes by hand.
5. **That's it** — every machine shows an address such as `127.0.0.3:13392` and a ⋮
   menu with "Connect over RDP", "Copy address" and more. You can also paste the address
   into your RDP/SSH client and connect.

## Worth knowing

- **Several VPNs at once** — each connection runs in its own isolated network
  namespace, so networks of different clients (even with identical IP ranges) never
  collide. Tunnel types can be mixed freely.
- **IPsec** — for FortiGate dial-up. Three sign-in variants: **IKEv1 + PSK +
  username/password (XAuth)** (the common one — this is how FortiClient connects),
  **IKEv1 with PSK only** and **IKEv2 with PSK only**. The address inside the client's
  network is assigned by the gateway (mode config). A token (FortiToken) is appended
  to the password, which is how XAuth takes it. Not supported: certificate and EAP
  authentication, as both would need the client's CA installed; use SSL-VPN in that case.
- **Language** — English by default, Polish available in ⚙ Settings. The choice is
  stored in the vault, so it travels with an exported configuration; the backend uses
  it too, so connection errors and logs speak the same language as the rest of the panel.
- **The vault** — profiles live in `vault.enc` in the data folder (see [Install](#install)),
  encrypted with the master password. The panel and the forwarded ports are reachable from
  this computer only (they listen on the `127.0.0.0/8` loopback).
- **Local ports** — the pool is `13391–13449`, and **every port gets its own loopback
  address**: `13391 → 127.0.0.2`, `13392 → 127.0.0.3`, … `13449 → 127.0.0.60`.
  A separate address per machine is necessary because Windows stores RDP credentials
  under `TERMSRV/<address>` **without the port** — on a shared `localhost` the saved
  passwords would overwrite each other. To change the pool, edit both compose files
  (`docker-compose.yml`, `packaging/docker-compose.yml`) **and** `app/connections.py`.
- **Updates**: once a day the panel asks the
  [project page](https://mysttic.github.io/Mysttic/tunnelbox/) whether a newer version
  exists (its releases live in the `Mysttic/Mysttic` repository, next to other programs'
  downloads) and shows a bar above the connection list: with the ZIP package on Windows the
  "⬆️ Update" button downloads and installs it without leaving the browser, with the
  registry install the bar shows the `docker compose pull` command. The check sends none of
  your data and can be turned off in ⚙ Settings. The details and the contract (tag
  `tunnelbox-vX.Y.Z`, file `tunnelbox-X.Y.Z.zip`) are in [`app/updates.py`](app/updates.py).
- **Code changes** — after every change just run `./start.sh` / `start.bat` again; it
  rebuilds the image with
  `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build`.
- **Stopping the panel** — `docker compose down` in the folder with `docker-compose.yml`
  (the program folder for the ZIP package).
- **Coming from FortiVPN 2**: Tunnelbox is the same program under a new name, installed
  from scratch. FortiVPN 2 does not offer it as an update, and Tunnelbox does not touch
  FortiVPN 2's container or data. To keep your connections, save them in FortiVPN 2 with
  ⚙ Settings → "⬇️ Export configuration", remove the old container
  (`docker rm -f fortivpn2-panel`, it holds port 25263 and the port pool), install Tunnelbox
  and load the file with "⬆️ Import" on its first screen, using the same master password.
  FortiVPN 2 already removed? Import its vault file instead:
  `%LOCALAPPDATA%\FortiVPN2\data\vault.enc` on Windows,
  `~/.local/share/fortivpn2/data/vault.enc` on macOS and Linux (with Docker Engine that file
  belongs to root, so make a copy you can read first:
  `sudo install -o "$USER" -m 600 ~/.local/share/fortivpn2/data/vault.enc ~/fortivpn2-vault.enc`).
  A source checkout keeps its `./data`, so there only the container has to go. Once
  everything works, delete `%LOCALAPPDATA%\FortiVPN2` (`~/.local/share/fortivpn2`) and the
  `fortivpn2-panel` images.

## Architecture (for the curious)

```
browser ── tunnelbox.localhost:25263 ── FastAPI (panel + API)
                                        │
                                container tunnelbox
                                        │
           per connection: netns "vpnN" ── openfortivpn (ppp0)
                                        │   or charon (IPsec policies)
                                        │
 127.0.0.X:1339X ── socat ── veth ── socat ── machine in the client's network
```

- `app/main.py` — the panel's API (profiles, connect/disconnect, certificate trust)
- `app/vault.py` — the encrypted vault of profiles (scrypt + AES-256-GCM)
- `app/connections.py` — network namespaces, tunnel lifecycle, port forwarding
- `app/ipsec.py` — strongSwan configuration and driving the daemon through swanctl
- `app/updates.py` — the daily check for a newer release
- `app/i18n.py`, `app/static/i18n.js` — English and Polish message catalogs
- `app/static/` — the browser interface

SSL-VPN and IPsec differ only in how the tunnel is established. openfortivpn creates a
`ppp0` interface and reports progress on stdout; IPsec creates no interface — traffic
is steered by an XFRM policy and a separate routing table (220), and the state is
established and checked through `swanctl`. Each tunnel gets its own `charon-systemd`
instance, because IPsec policies belong to a network namespace.

## Security

The panel and the forwarded ports listen on the `127.0.0.0/8` loopback only, saved profiles
are encrypted with your master password (scrypt + AES-256-GCM), and apart from your VPN
tunnels the only connection the panel makes by itself is the daily update check, which you
can turn off. The threat model, and how to report a vulnerability without opening a public
issue: [SECURITY.md](SECURITY.md).

## License

Tunnelbox's own code is released under the [MIT License](LICENSE). The image also carries
openfortivpn, strongSwan, pppd, socat and other components under their own licenses; they
run as separate programs, and [THIRD_PARTY.md](THIRD_PARTY.md) lists them together with where
to find their exact versions and sources.

## Contributing

Bug reports, ideas and pull requests are welcome — [CONTRIBUTING.md](CONTRIBUTING.md) covers
the branches (`develop` → `main`), the commit convention, running the tests and refreshing the
manual's screenshots. Publishing a release (for the maintainer):
[docs/RELEASING.md](docs/RELEASING.md) — a release is built automatically when `develop` is
merged into `main`.
