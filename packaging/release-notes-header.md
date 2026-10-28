**Tunnelbox __VERSION__** — several Fortinet (FortiGate) SSL-VPN and IPsec VPNs at once,
straight from your browser; the tunnels run inside a Docker container.

*Formerly FortiVPN 2 · not affiliated with or endorsed by Fortinet.*

## Installation (Windows)

1. Install and start **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**.
2. Download **`tunnelbox-__VERSION__.zip`** below and unpack it into any folder.
3. Double-click **`start.bat`** (Mac/Linux: `./start.sh`).
4. The panel opens in your browser at **http://tunnelbox.localhost:25263**.

The package carries a ready-made Docker image — `start.bat` loads it locally
(`docker load`); nothing is built and nothing is pulled from a registry. It works without
internet access (beyond Docker Desktop itself). The panel speaks English by default and
Polish on request (⚙ Settings → Language). Full manual: `docs/MANUAL.md` in the package
(`docs/MANUAL.pl.md` in Polish).

**Coming from FortiVPN 2?** Tunnelbox installs from scratch and does not take over
FortiVPN 2. Export your connections in FortiVPN 2 (⚙ Settings → "⬇️ Export configuration"),
remove its container (`docker rm -f fortivpn2-panel`), install this package and load the
file with "⬆️ Import" on the first screen. Details: "Coming from FortiVPN 2" in the
package's `README.md`.

## Docker (any OS)

Images for `linux/amd64`, `linux/arm64` and `linux/arm/v7`:

```sh
docker pull ghcr.io/mysttic/tunnelbox:__VERSION__
```

Or install with one command, as in the README — it fetches the compose file and starts the
newest version (`latest`), keeping data in `./data`:

```sh
curl -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml && docker compose up -d
```

In Windows PowerShell 5.1 use `curl.exe` and run the two commands separately. Update later
with `docker compose pull`, then `docker compose up -d`. On macOS, add the loopback aliases first
([README → macOS: loopback aliases](https://github.com/Mysttic/tunnelbox#macos-loopback-aliases)).
