# Contributing to Tunnelbox

Thanks for helping! Bug reports and ideas go to
[issues](https://github.com/Mysttic/tunnelbox/issues); security problems do **not** — see
[SECURITY.md](SECURITY.md). By contributing you agree that your work is released under the
project's [MIT License](LICENSE).

## Branches

- **`develop`** is where work happens. Branch off it and open your pull request against
  `develop`.
- **`main`** holds releases only. A release is a `develop` → `main` pull request that bumps
  [`VERSION`](VERSION) and adds a [`CHANGELOG.md`](CHANGELOG.md) section; merging it builds
  and publishes everything — see [docs/RELEASING.md](docs/RELEASING.md).

Mention user-visible changes in the pull request description; they go into the changelog
when the next version is released.

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/), and every
commit of a pull request is checked by commitlint (the "Konwencja commitów (commitlint)"
check, configured in [`.commitlintrc.json`](.commitlintrc.json)):

```text
feat(ipsec): support IKEv2 with a pre-shared key
fix: keep the update bar hidden after "Later"
docs: explain the macOS loopback aliases
chore(deps): bump fastapi
```

Mark a breaking change with `!` after the type (`feat!: …`) or a `BREAKING CHANGE:` footer.
The description may be in English or Polish. To check your commits before pushing:

```bash
npx --yes -p @commitlint/cli@21.2.3 -p @commitlint/config-conventional@21.2.3 \
  commitlint --from origin/develop --to HEAD
```

## Tests

CI runs them on every pull request, and they have to be green before merging. Locally:

```bash
# backend (pytest)
pip install -r app/requirements-dev.txt
python -m pytest tests -q

# frontend e2e (Playwright)
cd tests/e2e && npm ci && npx playwright install chromium && npx playwright test
```

To try the whole thing for real, run `./start.sh` (or `start.bat` on Windows) in the
repository — it builds the image from source and starts the panel at
<http://tunnelbox.localhost:25263>.

## Screenshots

After changing the interface, refresh the manual's screenshots (both languages, one
command) and commit them with the change:

```bash
node tools/screenshots.js
```

It uses Playwright from `tests/e2e`, so install that first (see above).
`tests/test_docs.py` fails when a screenshot is missing, unused or unknown to the generator.

## Languages

- **Interface texts** live in two catalogs — [`app/static/i18n.js`](app/static/i18n.js)
  for the browser and [`app/i18n.py`](app/i18n.py) for backend messages. Add every new
  key in **both English and Polish**; `tests/test_i18n.py` checks that the keys and
  placeholders match and that nothing is unused.
- **User documentation** is bilingual and mirrored: `README.md` / `README.pl.md`,
  `docs/MANUAL.md` / `docs/MANUAL.pl.md`, `packaging/INSTALL.md` / `packaging/INSTALL.pl.md`.
  Change both sides. Maintenance documents (this file, `CHANGELOG.md`, `SECURITY.md`,
  `THIRD_PARTY.md`, `docs/RELEASING.md`) are English only.
- **Code comments, docstrings and test names are in Polish**, like the rest of the
  codebase — match the surrounding code. Messages printed by the start-up scripts are in
  English.
- `.ps1` files must stay UTF-8 **with a BOM** and CRLF line endings, and work in Windows
  PowerShell 5.1 (no `&&`, `??` or other PowerShell 7-only syntax) — `tests/test_packaging.py`
  checks the BOM.
