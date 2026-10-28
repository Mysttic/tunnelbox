# Tunnelbox — installation

*🇬🇧 English · [🇵🇱 Polski](README.pl.md)*

A panel for connecting to Fortinet VPNs (SSL-VPN and IPsec), operated entirely from your
browser. Tunnelbox, formerly FortiVPN 2 (its name up to version 2.9), is not affiliated with
or endorsed by Fortinet.

## Getting started (3 steps)

1. Install and start **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**
   (on Linux, Docker Engine is enough).
2. Double-click **`start.bat`** (Windows) or run `./start.sh` (Mac/Linux). The script
   loads the bundled image (`tunnelbox-image-X.Y.Z.tar.gz`) into Docker (`docker load`)
   and starts the panel — nothing is built and nothing is downloaded from the internet.
   On a Mac it asks for your password once to add the local addresses the panel needs
   (they disappear after a reboot — just run `./start.sh` again then).
3. The panel opens by itself at **http://tunnelbox.localhost:25263**.

The panel runs in the background — no terminal window to keep open.

## Language

The panel starts in English. To switch to Polish: **⚙ Settings → Language → Polski**.
The choice covers the whole interface, including messages coming from connections, and
it is saved with your configuration.

## Fast RDP connect

This works out of the box — `start.bat` sets it up. Clicking "Connect over RDP" in the
panel opens remote desktop straight at the machine's address — no `.rdp` file is saved,
so Windows does not warn about an "unknown publisher" on every connection, and the
clipboard works immediately. The first time, your browser asks for permission to open
the application — tick "Always allow".

Don't want it? In the panel: **⚙ Settings → Fast RDP connect** — the button then turns
into "Download .rdp file".

## Full manual

The step-by-step guide with screenshots is in **[docs/MANUAL.md](docs/MANUAL.md)**
in this package (Polish: **[docs/MANUAL.pl.md](docs/MANUAL.pl.md)**).

## Updating

The panel watches its own version. When a newer one appears, a bar shows up above the
connection list with an **"⬆️ Update"** button — one click downloads the package and
installs it in the background (a separate window shows the progress). Nothing to unpack.

You can also do it the old way: download the package from the
[project page](https://mysttic.github.io/Mysttic/tunnelbox/), unpack it **anywhere** and
run `start.bat`. The rest happens by itself: the script moves your saved
connections over from the previous version, removes its container and image, then starts
the new one.

Update checks can be turned off: **⚙ Settings → Check for updates**. The check sends
none of your data — it only asks for the list of releases.

Your connections (`vault.enc`) live outside the program folder, in
`%LOCALAPPDATA%\Tunnelbox\data` (Mac/Linux: `~/.local/share/tunnelbox/data`), so it does
not matter where you unpack the package. Your master password and panel settings stay as
they were.

## Coming from FortiVPN 2

Tunnelbox is FortiVPN 2 under a new name, but it installs from scratch: FortiVPN 2 does not
update to it, and this package leaves FortiVPN 2's container and data alone. To bring your
saved connections along:

1. In FortiVPN 2: **⚙ Settings → "⬇️ Export configuration"**. You get an `.enc` file,
   encrypted with your master password.
2. Remove FortiVPN 2's container, which holds the panel's port:
   `docker rm -f fortivpn2-panel` (or delete it in Docker Desktop → Containers).
3. Install Tunnelbox as described above.
4. On Tunnelbox's first screen click **"⬆️ Import"**, pick the exported file and type the
   same master password.

Already removed FortiVPN 2? Import its vault file instead:
`%LOCALAPPDATA%\FortiVPN2\data\vault.enc` (Mac/Linux:
`~/.local/share/fortivpn2/data/vault.enc`; on Linux with Docker Engine that file belongs to
root, so copy it with `sudo` first). Once everything works, delete the
`%LOCALAPPDATA%\FortiVPN2` folder (Mac/Linux: `~/.local/share/fortivpn2`) and the
`fortivpn2-panel` images in Docker Desktop → Images. Your bookmark changes too: the panel
now opens at **http://tunnelbox.localhost:25263**.

## Stopping

Run `docker compose down` in the program folder.

## Something is not working?

- **"Image file … not found"** — unpack the **whole** ZIP package (the
  `tunnelbox-image-*.tar.gz` file has to sit next to `start.bat`).
- **"Docker not found"** — install Docker Desktop (on Linux, Docker Engine) first.
- **"Docker is not running"** — start Docker Desktop and wait until it is fully up.
- **"Could not add the loopback alias …"** (Mac) — run `./start.sh` again and enter your
  password when `sudo` asks for it.
