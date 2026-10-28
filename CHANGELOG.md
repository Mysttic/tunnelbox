# Changelog

Every notable change to **Tunnelbox** (formerly FortiVPN 2). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/).

When releasing a new version, **add a section here** for the number in the `VERSION`
file — the release workflow pulls it into the GitHub release notes automatically.

## [3.0.0] — 2026-10-18

### Changed
- **FortiVPN 2 is now Tunnelbox.** The program has a new name and a new
  [project page](https://mysttic.github.io/Mysttic/tunnelbox/), and its code is released
  under the [MIT License](LICENSE). It still connects to Forti SSL-VPN and IPsec gateways
  exactly as before. Tunnelbox is an independent project, not affiliated with or endorsed
  by Fortinet.
- **A clean install, not an update.** Tunnelbox does not take over FortiVPN 2: a 2.9.x
  panel does not offer this version, and the package leaves FortiVPN 2's container, images
  and data alone. To keep your saved connections, export them in FortiVPN 2 (⚙ Settings →
  "⬇️ Export configuration"), remove its container (`docker rm -f fortivpn2-panel`, it
  holds port 25263 and the port pool), install Tunnelbox and load the file with
  "⬆️ Import" on its first screen, using the same master password. Exports from 2.9.x, and
  FortiVPN 2's own `vault.enc`, import unchanged. Afterwards `%LOCALAPPDATA%\FortiVPN2`
  (macOS/Linux: `~/.local/share/fortivpn2`) and the `fortivpn2-panel` images can be
  deleted.
- **Everything follows the new name**: the panel's address,
  **`http://tunnelbox.localhost:25263`**, the package `tunnelbox-X.Y.Z.zip`, the container
  `tunnelbox` (`docker exec tunnelbox /diagnose.sh`), the data directory
  `%LOCALAPPDATA%\Tunnelbox\data` (macOS/Linux: `~/.local/share/tunnelbox/data`),
  downloaded versions in `%LOCALAPPDATA%\Tunnelbox\versions`, the compose variable
  `TUNNELBOX_DATA`, the Windows protocols `tunnelbox-rdp://` and `tunnelbox-update://` and
  exported configurations named `tunnelbox-config-<date>.enc`. Port 25263, the pool 13391
  to 13449 and the loopback addresses 127.0.0.2 to 127.0.0.60 stay the same, so the RDP
  passwords Windows has saved per machine keep working.
- **A new update channel.** The panel ([`app/updates.py`](app/updates.py)) and the
  Windows update helper look for releases tagged `tunnelbox-vX.Y.Z` with the file
  `tunnelbox-X.Y.Z.zip` in `Mysttic/Mysttic`, the repository behind the project page, and
  the helper accepts downloads only from
  `https://github.com/Mysttic/Mysttic/releases/download/`.
- **The start-up scripts speak English**, like the panel by default — `start.bat`,
  `start.sh` and the update and RDP helpers print their messages in English.
- **CI runs on every pull request**, to `develop` and to `main`, instead of only on
  `develop` → `main`.
- **The release workflow runs with least privilege**: no permissions at the top level, and
  each job asks only for what it needs (publishing packages only for the image job, issues
  only for the failure report).

### Added
- **Ready-made images in a registry** — `ghcr.io/mysttic/tunnelbox` and, on Docker Hub,
  `mysttic/tunnelbox`, built by the release workflow for **`linux/amd64`, `linux/arm64` and
  `linux/arm/v7`** and tagged `X.Y.Z`, plus `X.Y` and `latest` for the newest release (a
  re-run of an older release never moves them back). The GitHub release appears only once
  the image is in GHCR, and a Docker Hub outage never holds the release back. Installed
  from the registry,
  Tunnelbox runs natively on Apple Silicon Macs, Raspberry Pis and ARM servers (the ZIP
  package keeps carrying the `linux/amd64` image). On `linux/arm/v7` the `cffi` wheel is
  compiled in a separate build stage, so the compiler never reaches the image.
- **One-command install.** The [`docker-compose.yml`](docker-compose.yml) in the repository
  root now installs from the registry: download that single file and run
  `docker compose up -d` — nothing to unpack. Running from source moved to an overlay,
  [`docker-compose.build.yml`](docker-compose.build.yml), which the repository's
  `start.sh` / `start.bat` add on their own.
- **The update bar knows how the panel was installed.** A registry install
  (`TUNNELBOX_INSTALL=registry`) shows the commands to update with — `docker compose pull`,
  then `docker compose up -d`, as two commands so they work in Windows PowerShell 5.1 too —
  instead of the "⬆️ Update" and
  "⬇️ Download package" buttons, which only make sense for the ZIP package.
- **The Docker Hub description follows the README** — synced on every release.
- **macOS: the loopback aliases are added for you.** Docker Desktop for Mac cannot publish
  ports on 127.0.0.2–127.0.0.60 until those addresses exist on `lo0`; `./start.sh` adds
  the missing ones with `sudo` (asking for your password once) and says why. The aliases
  disappear after a reboot — run `./start.sh` again then.
- **A failed release opens an issue.** If any release job fails, a `release-failed` issue
  titled `Release vX.Y.Z failed` lists the jobs that failed and links the run; a re-run
  that fails again comments on the same issue instead of opening another.
- **Commit messages are checked** — [Conventional Commits](https://www.conventionalcommits.org/),
  enforced by commitlint ([`.commitlintrc.json`](.commitlintrc.json)) as the CI check
  "Konwencja commitów (commitlint)".
- **The paperwork of an open project**: [`LICENSE`](LICENSE) (MIT),
  [`THIRD_PARTY.md`](THIRD_PARTY.md) (every component in the image, its license and how to
  get its source), [`SECURITY.md`](SECURITY.md) (supported versions, private reporting and
  the threat model), [`CONTRIBUTING.md`](CONTRIBUTING.md), and an issue template for bug
  reports with a link to private vulnerability reporting.
- **Every release lists the exact versions of its components** —
  `THIRD_PARTY_VERSIONS.txt` in the ZIP and `/usr/share/doc/tunnelbox/third-party-versions.txt`
  in the image (next to `LICENSE` and `THIRD_PARTY.md`): the Debian packages with their
  source packages, and the Python packages.
- **Dependabot** opens weekly pull requests against `develop` for the Python dependencies,
  the e2e toolchain and the GitHub Actions, with minor and patch bumps grouped.

### Security
- **The panel answers only to this computer's names** — `127.0.0.1`, `localhost` and
  `*.localhost`; any other `Host` header gets HTTP 400. Listening on the loopback alone did
  not stop a web page that points its own domain at `127.0.0.1` (DNS rebinding) from
  calling the API as if it were the panel, e.g. downloading the encrypted vault, which
  works without unlocking.
- **Vulnerabilities are reported privately** — through GitHub's private vulnerability
  reporting, never in a public issue; see [`SECURITY.md`](SECURITY.md).
- **The history is scanned for secrets** with [`.gitleaks.toml`](.gitleaks.toml) on top of
  gitleaks' default rules. The made-up
  passwords in the tests and the screenshot generator now look made up
  (`example-password`), so other people's scanners do not report them as leaks.
- **Why the container runs privileged** is documented in the README, together with what
  it needs that access for — Tunnelbox still listens only on `127.0.0.0/8`.

### Removed
- **FortiVPN 2's downloads.** The `fortivpn2-v*` releases and the `fortivpn2/` page are
  gone from the download site; its old address leads to the Tunnelbox page.

## [2.9.0] — 2026-09-08

### Added
- **English and Polish, picked in ⚙ Settings.** The panel now starts in **English** and
  switches to Polish from a single setting — no page reload, and the choice covers
  everything: static texts, connection cards, dialogs, validation errors, messages from the
  tunnels and the lines in the connection log. It is stored in the vault, so it travels
  with an exported configuration, and mirrored to the browser so the master-password screen
  already speaks the right language before anything is read from the vault. Two catalogs
  hold the texts — [`app/static/i18n.js`](app/static/i18n.js) for the browser and
  [`app/i18n.py`](app/i18n.py) for the backend — and `tests/test_i18n.py` keeps them in
  step: same keys in both languages, same placeholders, nothing missing and nothing unused.
- **Bilingual documentation.** The readme and the user manual come in both languages
  (`README.md` / `README.pl.md`, `docs/MANUAL.md` / `docs/MANUAL.pl.md`), each with its own
  set of screenshots (`docs/img/en`, `docs/img/pl`) generated in one pass. The package ships
  both. Maintenance documents are English only; `RELEASING.md` moved to `docs/RELEASING.md`.

### Changed
- **`tools/screenshots.js` renders both languages in one run**, sample machine names
  included, into `docs/img/en` and `docs/img/pl`. `tests/test_docs.py` checks that both
  manuals show the same set of pictures and that nothing is left over outside a language
  directory.
- **Errors carry a code where the panel needs to recognise them.** Suppressing the harmless
  "already active" alert used to match on the Polish message text, which stops working the
  moment the message can be English; the connect endpoint now returns a `code` alongside it.

## [2.8.0] — 2026-09-08

### Added
- **Updating from inside the panel.** Once a day the panel asks the download page for a
  newer version and shows a bar above the connection list: version number, release date
  and package size. On Windows the **"⬆️ Update"** button downloads the package, unpacks
  and installs it — keeping your saved connections, exactly like a manual update. Outside
  Windows (and when the installer is not registered) you get **"⬇️ Download package"**.
  The **"Later"** button hides the bar until the browser is closed.
- **A "Check for updates" setting** together with a **"🔄 Check now"** button
  (⚙ Settings). Turning it off means literally that the panel connects to nothing except
  your own VPN tunnels. The check sends no user data, and when the page does not answer,
  the panel simply shows no bar and carries on.
- **The `fortivpn-update://` helper** (`packaging/update-launcher.ps1`), registered by
  `start.bat` next to the existing `fortivpn-rdp://`. From the page it receives **only a
  version number** — it resolves the file address itself by asking the releases page, and
  checks its origin and size before unpacking. The new version lands in
  `%LOCALAPPDATA%\FortiVPN2\wersje`, and earlier packages in that directory are removed
  only after the panel is confirmed to be running the new version.
- **Copying releases to the download page** (the `Mysttic/Mysttic` repository). After a
  release is created, a separate job copies the package under the tag
  `fortivpn2-v<version>` and deletes this project's earlier releases, so exactly one —
  the newest — version stands on the page. It needs the `HUB_TOKEN` secret; see
  `docs/RELEASING.md`. The panel asks that page rather than its own repository: a private
  repository answers 404 to everyone but its owner, so the check would silently never
  find an update.


### Changed
- **`start.bat` will not roll the version back silently.** Updating from the panel leaves
  the old package folder on disk; run by mistake, it now asks for confirmation before
  installing a version older than the running one (by default it keeps the newer one and
  opens the panel).
- Protocol registration in `packaging/start.ps1` moved into a shared `Register-Handler`
  function serving both `fortivpn-rdp://` and `fortivpn-update://`.
- **The user manual was refreshed.** The screenshots predated IPsec and the settings
  dialog — they showed a header with a single button. The whole set was retaken on the
  current version, with new pictures of the IPsec form, the ⋮ menu next to a machine,
  adding a machine to a running connection, the settings window and the update bar. A new
  **Panel settings** section gathers fast RDP connect, update checks and configuration
  export/import in one place (they used to be scattered through the text).
- **`tools/screenshots.js`** — manual screenshots are now produced by a single command
  (`node tools/screenshots.js`) against stubbed API responses, so refreshing them after an
  interface change needs no clicking or cropping. `tests/test_docs.py` keeps the manual and
  the screenshot directory from drifting apart.

## [2.7.0] — 2026-09-04

### Added
- **IPsec connections** alongside the existing Forti SSL-VPN. The form gained a
  **Connection type** field; choosing IPsec reveals its own set of fields (PSK, sign-in
  method, identifiers, networks behind the VPN, aggressive mode) and hides the SSL-VPN
  ones (port, realm). Previously saved profiles keep working unchanged — a missing field
  means SSL-VPN, so the vault needs no migration.
- **Three IPsec sign-in variants:** *IKEv1 + PSK + username and password (XAuth)* — the
  default, how a typical FortiGate dial-up works and how FortiClient connects — plus
  *IKEv1* and *IKEv2 with PSK only*, which ask for no user (the panel then hides the
  username and password). The address inside the client's network is assigned by the
  gateway (mode config).
- **Token (FortiToken) with IPsec** — the one-time code is appended to the password, just
  as FortiClient does with XAuth. Approval on a phone (push) stayed with SSL-VPN, because
  IPsec has no way to carry it; the panel hides the option and rejects it in the API.
- **An `IPsec` badge on the connection card** — only for IPsec tunnels, so the list shows
  at a glance which is which. SSL-VPN stays unlabelled.
- **Error messages for IPsec** — the strongSwan log is turned into concrete advice:
  rejected sign-in, wrong PSK, no shared ciphers, rejected network range, a silent
  gateway (with a hint about UDP ports 500/4500) and missing IPsec support in the kernel.
  The daemon's start-up noise about absent plugins no longer reaches the panel's log.
- **IPsec diagnostics** — for IPsec tunnels, `docker exec fortivpn2-panel /diagnose.sh`
  shows the SA state, XFRM policies and routing table 220 instead of looking for a `ppp`
  interface, which IPsec never creates. The same goes into the connection log in the panel.

### Changed
- **The image ships strongSwan** (`strongswan`, `strongswan-swanctl`, `charon-systemd`,
  the XAuth and cryptographic plugins). Every IPsec tunnel gets its own `charon-systemd`
  instance in its own network namespace — IPsec policies belong to a netns, and the
  "systemd" variant does not guard a PID file at a fixed path, so several tunnels can run
  in parallel. Files holding passwords and the PSK live in a 0700 directory and are
  removed together with the tunnel.
- **Username and password are no longer unconditionally required** — with IPsec on a PSK
  alone the gateway asks for no user. For SSL-VPN and for XAuth the requirement is unchanged.

## [2.6.1] — 2026-08-12

### Added
- **The version number in the panel header** — next to the title, e.g. `v2.6.1`. It is
  visible on the master-password screen too, so the version can be checked without signing
  in. The source is the repository's `VERSION` file: the image copies it next to the code,
  and when running from source the panel reads it from the project directory — nothing to
  write by hand at release time, a bumped `VERSION` is enough.

## [2.6.0] — 2026-08-12

### Changed
- **"Connect over RDP" no longer asks for permission on every connection.** The panel
  starts remote desktop straight at the machine's address (`mstsc /v:`) instead of saving
  and opening a `.rdp` file. The reason: the April 2026 Windows security update
  (CVE-2026-26151) warns about an "unknown publisher" on **every** opening of an unsigned
  `.rdp` file — with no "do not ask again" — and disables the clipboard and printers for
  that session. A connection started by address is not affected: no window appears, and
  the clipboard and printers work immediately because they come from the user's own remote
  desktop settings. Saved passwords are untouched — Windows keeps them under
  `TERMSRV/<address>`, and every machine has its own loopback address.

### Removed
- **The `%LOCALAPPDATA%\FortiVPN2\rdp` directory is no longer used** — the helper neither
  creates nor refreshes `.rdp` files. Old files can be deleted; window settings are taken
  over by remote desktop's `Default.rdp`. The **"⬇️ Download .rdp file"** button
  (⚙ Settings → "Fast RDP connect" off) works as before.

## [2.5.0] — 2026-08-11

### Added
- **Configuration file export and import** — buttons in ⚙ Settings and on the sign-in
  screen. Export writes every connection into a single `.enc` file (still encrypted with
  the master password) — for a backup or for moving to another computer. Import requires
  the password for the chosen file, so the configuration cannot be replaced by a random
  file; the previous version is saved beside it as a `vault-<date>.enc.bak` copy.

### Changed
- **"Lock panel" no longer drops active connections.** The lock covers access to the
  configuration — VPN tunnels keep running, and after unlocking with the master password
  they are all still there. Locking also clears the view, and going back with the
  browser's back/forward buttons verifies the session on the server — there is no way to
  slip past the lock or see a remembered connection list.
- **The panel has its own address: `http://fortivpn.localhost:25263`** (previously
  `http://localhost:8080`). Why: `localhost:8080` is often taken by other tools, and in
  the browser's "open this application?" dialog — shown by **Connect over RDP** — such an
  address gave no clue which program was asking. Now it shows a real name.
  Browsers resolve `*.localhost` names to the loopback themselves, so no `hosts` entry and
  no administrator rights are needed. The panel still listens locally only (`127.0.0.1`)
  and is invisible from the network.

  > If you have a bookmark to the old address, update it.
  > The start-up scripts query the panel by IP (`127.0.0.1:25263`), because the system
  > resolver does not handle `*.localhost` names — only browsers do.

## [2.4.1] — 2026-08-10

### Fixed
- **An update could start with an empty configuration.** Moving saved connections across
  only worked while the previous version's container still existed — and it disappears
  after `docker compose down` (the recommended way to stop the panel). The configuration
  is now also looked for in the package folder, the parent folder and in neighbouring
  installations.
- **On Windows the migration silently did nothing.** PowerShell stripped the quotes from
  the argument passed to `docker.exe`, so reading the previous version's data location
  failed on a template error and was ignored.
- **An installation can no longer lose the configuration.** It follows a
  *protect → install → import → confirm* sequence: before anything changes, the
  configuration goes into a working copy; after the new version starts it is loaded back,
  and the copy is deleted **only once confirmed** that the panel sees it and the files are
  identical. If confirmation fails, the copy stays and the script prints its path and how
  to restore it. An existing configuration is never overwritten silently.
- **Cleaning up old images also removed `fortivpn2-panel:latest`** (the image built
  locally from source). Only tags that look like an `X.Y.Z` version are deleted now.

## [2.4.0] — 2026-08-10

### Added
- **Fast RDP connect, without downloading a file every time.** Clicking "Connect over RDP"
  opens remote desktop immediately — it is set up at start-up (`start.bat`), with nothing
  to run by hand from a console (the protocol is registered for the current user only, no
  administrator rights). `.rdp` files go into one directory
  (`%LOCALAPPDATA%\FortiVPN2\rdp`) instead of littering Downloads, and on later
  connections the existing file is reused (keeping your settings and the saved password);
  only the address is refreshed, in case the machine's port changed.
- **Panel settings** (⚙ in the header) — the **"Fast RDP connect"** switch decides which
  button the ⋮ menu shows: "🖥️ Connect over RDP" (default) or "⬇️ Download .rdp file".
  The Windows-side configuration always exists, so switching needs nothing extra. Settings
  are stored in the encrypted vault.
- The `.rdp` file is created automatically on the first connection — no need to download
  or copy it anywhere beforehand.
- **A safety net for when remote desktop does not open** — if fast connect is not set up
  on a given computer, the panel shows a hint after a moment with a "⬇️ Download .rdp file"
  button and a shortcut to the settings, instead of leaving the user with a button that
  does nothing.

### Fixed
- **Updating lost the configuration and refused to start.** The package unpacks into a
  folder named after the version, so the new version landed next to the old one: the vault
  (`data/vault.enc`) stayed in the previous folder, and the old container with the same
  name held on to the name and port 8080. Now `start.bat` does everything itself — it
  moves saved connections from the previous installation, removes its container and image,
  then starts the new version. User data lives outside the program folder
  (`%LOCALAPPDATA%\FortiVPN2\data`), so where you unpack no longer matters.
- **Polish characters in `start.bat` messages showed up as gibberish.** Windows PowerShell
  5.1 reads `.ps1` files without a BOM as ANSI; the scripts are now saved as UTF-8 with a
  BOM. That also removes the risk of an em dash breaking string parsing and killing the
  script with a syntax error.

## [2.3.0] — 2026-08-07

### Added
- **Adding a machine to a running connection** — the "＋ Add machine" button on a connected
  profile's card. The new forwarding starts immediately, with no disconnect and no signing
  in to the VPN again.
- **Opening in a browser recognised from the machine name** — if the name contains
  `http`/`https` (or `www`, "strona"), the ⋮ menu offers "Open in browser" even on a
  non-standard port (e.g. 9443). `rdp`, `ssh` and `vnc` are recognised too.
- **Changing the master password** — the "Change master password" button in the header
  opens a dialog where, after giving the current password, you set a new one; the vault is
  then re-encrypted with it (with no loss of saved connections).

### Fixed
- **Windows overwrote saved RDP passwords between machines.** Remote desktop credentials
  go into Credential Manager under `TERMSRV/<address>` — **without the port**. All machines
  sat under a shared `localhost:<port>`, so they shared one entry and every new sign-in
  erased the previous one. Every local port received its own loopback address
  (`13391 → 127.0.0.2`, `13392 → 127.0.0.3`, … `13449 → 127.0.0.60`), so Windows remembers
  the password separately per machine.
- **A downloaded `.rdp` file asked for credentials even when they were saved** —
  `prompt for credentials:i:1` forced a prompt on every start. It is `:i:0` now.

### Changed
- The machine address shown in the panel, copied by the button, put into the `mstsc`/`ssh`
  command and into the `.rdp` file is now `127.0.0.X:<port>` instead of `localhost:<port>`.
  The number of published ports does not change — they are only spread across loopback
  addresses, still unreachable from the network.

> **After updating**, download your `.rdp` files again — the ones saved earlier point at
> `localhost` and will keep overwriting each other's passwords.

## [2.2.0] — 2026-07-24

### Added
- **Previewing an active connection's settings without disconnecting** — while a
  connection is up, the "Edit" button turns into "Preview" and opens the form read-only
  (fields disabled, no way to save).

### Fixed
- **The second (and every later) parallel connection timed out.** The transfer subnet
  between the container and the connection's network namespace used the link-local
  `169.254.<index>.0/30`, which collided with FortiGate's PPP peer address
  (`169.254.2.1`) — the gateway pushed a `169.254.2.1 dev ppp0` route, so forwarding
  replies for connection no. 2 escaped into the tunnel. The transit moved to
  `203.0.113.0/24` (TEST-NET-3, RFC 5737) — an address reserved for documentation, absent
  from client networks and from PPP addresses.
- **A connection could not be added when the FortiGate gateway address carried a
  realm/path** (e.g. `https://vpn.client.com:443/myrealm`). A "Realm / path" field was
  added, along with automatic splitting of a pasted full address into host, port and realm;
  the realm goes into the openfortivpn configuration. This also fixes push authorisation
  for such gateways.
- A downloaded `.rdp` file now carries the connection name (e.g.
  "Client Alfa - RDP server.rdp") — several connections may have a machine called
  "RDP server", so machine names alone kept colliding.
- `tools/diagnose.sh` uses `ps -e` (so it sees every socat process).

## [2.1.0] — 2026-07-24

### Added
- Two-factor token modes: **one-time code** (typed) and **approval in an app (push)** —
  chosen in the connection form.
- An **⋮** action menu next to a connected machine's address: connecting over RDP
  (downloading a `.rdp` file), SSH, VNC, opening in a browser, copying the address and a
  ready-made command.
- **Automatic service port completion** based on the machine name (e.g. "RDP" → 3389,
  "SSH" → 22, "VNC" → 5900).
- Tunnel diagnostics in the connection log, plus the `tools/diagnose.sh` tool
  (`/diagnose.sh` in the container) for looking into connectivity problems.
- Tests: backend (pytest) and e2e (Playwright), plus a **CI** workflow running on pull
  requests to `main`.

### Changed
- The connection log sticks to the bottom (newest entries) and keeps its scroll position
  despite the automatic refresh.

### Fixed
- Connections with a **push** token did not work — the panel forced `no-ftm-push`, which
  disabled the phone notification.
- Network hardening for several parallel tunnels (disabling `rp_filter`, per-veth
  forwarding) — fewer timeouts on the second connection.

### Reverted
- Manual local port selection — the port range is reserved when the container starts, so
  the port is assigned automatically.

## [2.0.0] — 2026-07-23

### Added
- Rebuilt from a terminal tool into a **web panel** (http://localhost:8080) operated
  entirely in the browser — no console, no OpenSSL, no editing files by hand.
- **An encrypted profile vault** — master password, scrypt + AES-256-GCM.
- **Isolation of several parallel VPN tunnels** (separate network namespaces), so client
  networks with identical IP ranges do not collide.
- Automatic handling of an unknown gateway certificate — one click instead of copying a
  fingerprint and encrypting files by hand.
- Port forwarding to machines in the client's network (`localhost:port` → RDP/SSH/…).
- **A self-contained release package** — the Docker image bundled into the ZIP
  (`docker load`), with no registry and no sign-in; a **Release** workflow after `develop`
  is merged into `main`.
- A full illustrated user manual (`docs/MANUAL.md`) with screenshots.
