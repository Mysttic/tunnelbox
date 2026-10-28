# Releasing a new version (for the maintainer)

A release is built automatically when a **`develop` → `main` pull request is merged**.
The pipeline ([.github/workflows/release.yml](../.github/workflows/release.yml)) runs these
jobs, in this order:

1. **`version`** — reads the number from the [`VERSION`](../VERSION) file (format `X.Y.Z`).
   If the tag `vX.Y.Z` already exists, it **skips the release** (the run ends green and all
   other jobs are skipped too).
2. **`images`** — builds the **registry image** for `linux/amd64`, `linux/arm64` and
   `linux/arm/v7` and pushes it to GHCR (`ghcr.io/mysttic/tunnelbox`), tagged `X.Y.Z`, plus
   `X.Y` and `latest` when this is the newest release.
3. **`release`** — only after `images`: builds the image `tunnelbox:X.Y.Z` (`linux/amd64`),
   packs a **self-contained ZIP** `tunnelbox-X.Y.Z.zip` — the image written by `docker save`
   (`tunnelbox-image-X.Y.Z.tar.gz`), the compose file, the start-up scripts, the
   documentation in both languages, `CHANGELOG.md`, `LICENSE`, `THIRD_PARTY.md` and
   `THIRD_PARTY_VERSIONS.txt` (the exact component versions, read from the image) — and
   creates the **GitHub Release** `vX.Y.Z` in this repository with the ZIP attached. Job
   `site` copies it to the download page, which is the update channel, so it must not
   appear before the image the registry install is then told to pull.
4. **`dockerhub`** — when configured, copies the same tags from GHCR to Docker Hub
   (`mysttic/tunnelbox`) without rebuilding and syncs the description from
   [`README.md`](../README.md). Nothing waits for it, so a Docker Hub problem never holds
   the release back.
5. **`site`**: copies the ZIP to the download page, the hub repository
   [`Mysttic/Mysttic`](https://github.com/Mysttic/Mysttic), as the release
   `tunnelbox-vX.Y.Z`. That copy is what the project page offers for download and what
   installed panels look for, see
   [The download page and the update channel](#the-download-page-and-the-update-channel-job-site).
6. **`report-failure`** — when any of the jobs above fails or runs out of time, opens an
   issue labelled `release-failed` (or comments on the open one).

The workflow grants no permissions at the top level (`permissions: {}`); each job asks only
for what it needs.

Users install Tunnelbox in one of two ways:

- **the ZIP package** from the [project page](https://mysttic.github.io/Mysttic/tunnelbox/):
  unpack, run `start.bat`, which loads the image locally (`docker load`); nothing is pulled
  from a registry;
- **the registry image** with the root [`docker-compose.yml`](../docker-compose.yml) —
  `docker compose up -d`, updated with `docker compose pull`, then `docker compose up -d`.

## How to release

1. **Bump [`VERSION`](../VERSION)** on the `develop` branch, e.g. to `3.1.0` (it has to
   differ from the previous one — otherwise the release is skipped). This is the step
   that is easiest to forget.
2. **Add a section to [`CHANGELOG.md`](../CHANGELOG.md)** for that number
   (`## [X.Y.Z] — YYYY-MM-DD` plus Added/Changed/Fixed). The release notes are
   [`packaging/release-notes-header.md`](../packaging/release-notes-header.md) followed by
   that section (under "Changes in this version"), and the changelog ships inside the
   package. If the section is missing, the workflow warns and the notes come out
   incomplete.
3. Open a `develop` → `main` pull request. **CI**
   ([.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs the backend and e2e tests
   and checks the commit messages — everything has to be green.
4. Merge the pull request. The **Release** workflow builds and publishes the release.
5. Done — no manual steps on GitHub. The registry image comes first, and it takes a while:
   `linux/arm/v7` and `linux/arm64` are built under emulation (up to about an hour on a
   cold cache). The release with the ZIP follows right after it.

> To ship a fix with no code change, bump `VERSION` alone and merge.

After releasing, it is worth checking that:

- the release `vX.Y.Z` with `tunnelbox-X.Y.Z.zip` is in this repository's Releases;
- the image tags exist for all three platforms —
  `docker buildx imagetools inspect ghcr.io/mysttic/tunnelbox:X.Y.Z` (and the same on
  Docker Hub, if configured);
- the release `tunnelbox-vX.Y.Z` with `tunnelbox-X.Y.Z.zip` stands on `Mysttic/Mysttic`,
  and no older `tunnelbox-v*` release is left there;
- the [project page](https://mysttic.github.io/Mysttic/tunnelbox/) shows the new number.

### When a job fails

A failure in any job — or a job that hits its time limit — runs **`report-failure`**: it
makes sure the `release-failed` label
exists, then comments the run's link on the open issue titled `Release vX.Y.Z failed`, or
opens that issue with the version, the jobs that failed and the run's link. GitHub's
notification is your alert.

Fix the cause (an expired token, a registry hiccup) and click **Re-run failed jobs** on the
failed run — the job gets the same inputs it had the first time, and the jobs that were
waiting for it (e.g. `release` after a failed `images`) run with it. Every publishing job
checks, at the moment it runs, whether its version is still the newest one: only then do
`latest` and `X.Y` move, does the GitHub release become *Latest*, does the copy on the
download page get replaced and does the Docker Hub description change. Re-running an older release's
failed run therefore never sends anyone back to that version.

The tag `vX.Y.Z` is created only when `release` succeeds:

- **`dockerhub` or `site` failed** — the tag exists, so a plain *Run workflow* or a push to
  `main` skips everything. Use **Re-run failed jobs**; *Run workflow* with the **force**
  input ticked skips the tag check and publishes anyway — use it only when re-running the
  failed job is no longer possible.
- **`images` or `release` failed** — there is no tag yet, so the next push to `main` (even
  without a `VERSION` change) or a plain *Run workflow* publishes `vX.Y.Z` from that newer
  commit. That is the way to ship a code fix for the failure: merge it without bumping
  `VERSION`, and do not re-run the old failed run afterwards. Until the release is out,
  merge nothing unrelated into `main`.

Close the issue once the release is complete.

## Registry images (job `images`)

The images are built with QEMU and buildx for `linux/amd64,linux/arm64,linux/arm/v7` and
pushed with the tag `X.Y.Z` and — when this is the newest release overall, or within its
`X.Y` line — `latest` and `X.Y`, with OCI labels for the title, the
description and the license (MIT). The layer cache lives in the Actions cache under its own
scope (`images`). The root `docker-compose.yml` points at `ghcr.io/mysttic/tunnelbox:latest`
and sets `TUNNELBOX_INSTALL: registry`, which makes the panel's update bar show
`docker compose pull` and `docker compose up -d` (two separate commands, so they also work in
Windows PowerShell 5.1) instead of the download buttons.

### GHCR (one-off setup)

GHCR needs no secret — the job signs in with the workflow's own `GITHUB_TOKEN`. But the
first push creates a new **package**, and a new package is **private**:

1. Open the `tunnelbox` package (Mysttic's profile → **Packages**) → **Package settings**.
2. **Change visibility** → **Public**. Without it `docker pull` asks everyone else to sign
   in, and the one-command install fails.
3. Make sure the package is linked to this repository (**Connect repository**, if the
   image's `org.opencontainers.image.source` label has not linked it already) and that
   this repository has write access under **Manage Actions access**.

### Docker Hub (optional)

The job `dockerhub` copies the tags from GHCR (`docker buildx imagetools create`), so Docker
Hub gets byte-for-byte the same image. Without these secrets it prints a warning and the
image stays in GHCR only — the run stays green. If the token expires, `dockerhub` fails and
opens a `release-failed` issue, but the release itself is already out.

1. On Docker Hub, create the repository `mysttic/tunnelbox` (public).
2. *Account settings → Personal access tokens* — a token with **Read, Write, Delete**
   access (updating the repository description needs it).
3. In this repository: *Settings → Secrets and variables → Actions → New repository
   secret* — `DOCKERHUB_USERNAME` (the Docker Hub user) and `DOCKERHUB_TOKEN` (the token).
4. Optionally, on the **Variables** tab, `DOCKERHUB_REPOSITORY` — to push somewhere other
   than the default `mysttic/tunnelbox`.

The full description on Docker Hub is `README.md` (relative links are turned into absolute
ones); the short description is set in the workflow and must stay within 100 characters.
Docker Hub limits the full description to 25,000 bytes.

## The download page and the update channel (job `site`)

Like the author's other programs, Tunnelbox is published through the hub repository
[`Mysttic/Mysttic`](https://github.com/Mysttic/Mysttic), which is also the download site
(GitHub Pages, [mysttic.github.io/Mysttic](https://mysttic.github.io/Mysttic/)). It keeps
the releases of several programs side by side, told apart by the tag prefix. Job `site`:

1. downloads exactly `tunnelbox-X.Y.Z.zip` from this repository's release `vX.Y.Z`;
2. creates the hub release `tunnelbox-vX.Y.Z` with that file, unchanged (titled
   `Tunnelbox X.Y.Z`, with the project page's address in the notes), **before** deleting
   the older `tunnelbox-v*` releases, so the page is never empty. The deletion filters on
   `^tunnelbox-v`, so it never touches releases of the other programs.

Once a day the panel ([`app/updates.py`](../app/updates.py)) asks
`https://api.github.com/repos/Mysttic/Mysttic/releases` whether a newer version exists, and
on Windows the update helper
([`packaging/update-launcher.ps1`](../packaging/update-launcher.ps1)) receives only a
version number from the page and resolves the download address there itself. The contract:

| What | Value | Read by |
|---|---|---|
| repository | `Mysttic/Mysttic` | panel, update helper, project page |
| release tag | `tunnelbox-vX.Y.Z` (drafts and pre-releases skipped) | panel, update helper, project page |
| package file | `tunnelbox-X.Y.Z.zip` | panel, update helper, project page |
| download origin | `https://github.com/Mysttic/Mysttic/releases/download/` | update helper (refuses anything else) |
| folder inside the ZIP | `tunnelbox-X.Y.Z/`, with `start.ps1` at its top | update helper (runs it after unpacking) |
| confirmation | `http://127.0.0.1:25263/api/vault` answers `"version": "X.Y.Z"` | update helper (waits for it) |

Changing any of them breaks updates **for people who already have the program**, and they
find out only when it stops working. If something has to change, first ship a version that
reads the new scheme and change the scheme after that. The consistency of the three places
(workflow, `app/updates.py`, `packaging/update-launcher.ps1`) is guarded by
`test_kontrakt_wydania_jest_ten_sam_w_trzech_miejscach` in
[`tests/test_packaging.py`](../tests/test_packaging.py).

FortiVPN 2 (2.9.x) read the same hub under the prefix `fortivpn2-v`. Tunnelbox does not
publish anything there, so a FortiVPN 2 panel never offers Tunnelbox: people move by
installing it from scratch and importing an export (README, "Coming from FortiVPN 2").

### The project page (in `Mysttic/Mysttic`)

The download pages are maintained in the hub repository, not here:

- **`tunnelbox/index.html`**: the download page; the shared `assets/releases.js` fills its
  button from the hub's releases:

  ```js
  initDownloads({
    tagPrefix: 'tunnelbox-v',
    files: [{ id: 'zip', match: /^tunnelbox-.*\.zip$/ }]
  });
  ```

- **`fortivpn2/index.html`**: only a redirect to `../tunnelbox/`, for old bookmarks and the
  "What's new" link of FortiVPN 2 panels;
- a row in the hub's `RELEASES.md` (project, page, prefix) and a card on its `index.html`.

### The `HUB_TOKEN` secret (one-off setup)

The default `GITHUB_TOKEN` only reaches the repository the workflow runs in, so copying to
the hub needs a credential of its own:

1. <https://github.com/settings/personal-access-tokens> — a **fine-grained** token.
2. Owner `Mysttic`, access limited to the `Mysttic/Mysttic` repository.
3. Permission **Contents: Read and write**.
4. In this repository: *Settings → Secrets and variables → Actions → New repository
   secret*, named `HUB_TOKEN`.

A missing `HUB_TOKEN` is a hard error: without the copy nobody can download the release and
no panel sees it, so the job fails and `report-failure` opens an issue. The token has an expiry date; when it runs out, the job
ends with a readable error, while the release in this repository and the registry images are
untouched. The fix: renew the token and **Re-run failed jobs** (see
[When a job fails](#when-a-job-fails)).

## Documentation and languages

The panel and its user-facing documentation are bilingual: English by default, Polish on
request. Maintenance documents (this file, the changelog, [`SECURITY.md`](../SECURITY.md),
[`CONTRIBUTING.md`](../CONTRIBUTING.md), [`THIRD_PARTY.md`](../THIRD_PARTY.md)) are English
only.

| Document | English | Polish |
|---|---|---|
| repository readme | [`README.md`](../README.md) | [`README.pl.md`](../README.pl.md) |
| user manual | [`docs/MANUAL.md`](MANUAL.md) | [`docs/MANUAL.pl.md`](MANUAL.pl.md) |
| readme inside the package | `packaging/INSTALL.md` | `packaging/INSTALL.pl.md` |

Interface texts live in two catalogs: [`app/static/i18n.js`](../app/static/i18n.js) for the
browser and [`app/i18n.py`](../app/i18n.py) for backend messages (validation errors,
connection errors, log lines). Both languages have to carry the same keys — that is what
[`tests/test_i18n.py`](../tests/test_i18n.py) checks, along with catching keys nothing uses
any more.

When the image gains a component (an apt package or a Python dependency), add it to
`THIRD_PARTY.md` — and, for an apt package, to the `dpkg-query` list in the
[`Dockerfile`](../Dockerfile) that writes the versions file.

## Screenshots in the manual

The manual shows the panel in pictures kept in `docs/img/en` and `docs/img/pl`. After an
interface change, refresh them with one command:

```bash
node tools/screenshots.js
```

The script serves `app/static`, stubs the API responses (no vault and no working VPN
needed) and overwrites the whole set in both languages. It takes Playwright from
`tests/e2e`, so it works after `cd tests/e2e && npm ci && npx playwright install chromium`.

The tests in [`tests/test_docs.py`](../tests/test_docs.py) keep the manuals and the
screenshot directories from drifting apart: every picture shown exists, none sits unused,
the generator knows them all, and the table of contents matches the headings.

## Tests

CI runs on **every pull request** — to `develop` and to `main` — and on demand
(*Run workflow*). Locally:

```bash
# backend (pytest)
pip install -r app/requirements-dev.txt
python -m pytest tests -q

# frontend e2e (Playwright)
cd tests/e2e && npm ci && npx playwright install chromium && npx playwright test
```

For CI to actually **block** a merge, protect `develop` and `main` on GitHub (branch
protection or a ruleset) and mark these checks as required:

- "Testy backendu (pytest)"
- "Testy e2e (Playwright)"
- "Konwencja commitów (commitlint)" — Conventional Commits, configured in
  [`.commitlintrc.json`](../.commitlintrc.json); it runs on pull requests only (see
  [CONTRIBUTING.md](../CONTRIBUTING.md)).

## Notes

- **Multi-architecture is done.** The registry images cover `linux/amd64`, `linux/arm64`
  (Apple Silicon, 64-bit Raspberry Pi OS, ARM servers) and `linux/arm/v7` (32-bit
  Raspberry Pi OS). The ZIP carries only the `linux/amd64` image — on Apple Silicon it runs
  under emulation, while the registry install runs natively.
- **`linux/arm/v7` compiles `cffi`** — PyPI has no ready-made wheel for it, so the
  Dockerfile builds the Python wheels in a separate `wheels` stage; the compiler stays in
  that stage and never reaches the image. Under emulation this is the slowest part of the
  `images` job, which is why it has a 60-minute timeout.
- The ZIP's size is mostly the image (~100–150 MB compressed).
- **Supply chain.** [Dependabot](../.github/dependabot.yml) opens weekly pull requests
  against `develop` for the Python dependencies (`/app`), the e2e toolchain
  (`/tests/e2e`) and the GitHub Actions, with minor and patch bumps grouped. Its commit
  messages (`chore(deps): …`) pass commitlint — the long lines it writes in commit bodies
  are why the body and footer line-length rules are off. The commitlint version in CI is
  pinned exactly, the e2e dependencies are locked by `package-lock.json` (`npm ci`), and
  every release records the exact versions inside its image (`THIRD_PARTY_VERSIONS.txt`,
  see [`THIRD_PARTY.md`](../THIRD_PARTY.md)).
