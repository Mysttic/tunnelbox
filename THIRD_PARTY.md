# Third-party components

Tunnelbox's own code — the panel in `app/`, the start-up and helper scripts, the Dockerfile
and the compose files — is released under the [MIT License](LICENSE). The Docker image that
runs it also carries other people's software: the VPN clients, the network tools, the
operating system and the Python libraries the panel is built on. This file lists them, says
under which license each one is distributed, and explains where to find the exact version
shipped in a given release and its source code.

The licenses named below are a summary. The binding text for every Debian package is its
copyright file inside the image, `/usr/share/doc/<package>/copyright`; for a Python package
it is the license file in its distribution on PyPI.

## Programs in the image

All of these are the unmodified binary packages of Debian 12 "bookworm", installed with
`apt-get` when the image is built.

| Component | Role in Tunnelbox | License | Upstream | Debian source package |
|---|---|---|---|---|
| openfortivpn | Forti SSL-VPN client — one process per SSL-VPN connection, inside that connection's network namespace | GPL-3.0-or-later with an OpenSSL exception | <https://github.com/adrienverge/openfortivpn> | `openfortivpn` |
| ppp (pppd) | the PPP daemon openfortivpn starts to bring up `ppp0` | BSD-style, with some files under other terms (see its copyright file) | <https://github.com/ppp-project/ppp> | `ppp` |
| strongSwan (`charon-systemd`, `swanctl`, `libstrongswan`, the standard, extra and extauth plugins) | IPsec (IKEv1/IKEv2) — one `charon-systemd` per IPsec connection, driven through `swanctl` | GPL-2.0-or-later, plugins included | <https://www.strongswan.org/> | `strongswan` |
| socat | port forwarding from `127.0.0.X:<port>` to a machine behind the VPN | GPL-2.0 | <http://www.dest-unreach.org/socat/> | `socat` |
| iproute2 (`ip`) | network namespaces, veth pairs, addresses, routes and XFRM state | GPL-2.0 | <https://wiki.linuxfoundation.org/networking/iproute2> | `iproute2` |
| iptables | NAT between the container and each connection's namespace | GPL-2.0 | <https://www.netfilter.org/projects/iptables/> | `iptables` |
| Python 3.11 | the interpreter that runs the panel | PSF-2.0 | <https://www.python.org/> | `python3.11` (the `python3` package comes from `python3-defaults`) |
| pip, with setuptools and wheel | install the Python libraries below when the image is built; they stay in the image | MIT | <https://pip.pypa.io/> | `python-pip`, `setuptools`, `wheel` |
| Debian 12 base (`debian:bookworm-slim`) and the packages pulled in with the above — coreutils, procps, ca-certificates and the rest | the operating system inside the container | various, per package | <https://www.debian.org/> | one per package — list them with `dpkg-query` (below) |

## Python libraries

The panel's direct dependencies are listed in [`app/requirements.txt`](app/requirements.txt);
the rest are pulled in by them. They are installed from PyPI wheels, not from Debian. On
`linux/arm/v7` PyPI has no ready-made `cffi` wheel, so the image build compiles it from its
source distribution (in a separate build stage — the compiler does not end up in the image).

| Package | Role in Tunnelbox | License | Upstream |
|---|---|---|---|
| fastapi | the web framework of the panel's API | MIT | <https://pypi.org/project/fastapi/> |
| uvicorn | the HTTP server the panel runs in | BSD-3-Clause | <https://pypi.org/project/uvicorn/> |
| cryptography | the vault: scrypt and AES-256-GCM | Apache-2.0 OR BSD-3-Clause | <https://pypi.org/project/cryptography/> |
| starlette | via fastapi | BSD-3-Clause | <https://pypi.org/project/starlette/> |
| annotated-doc | via fastapi | MIT | <https://pypi.org/project/annotated-doc/> |
| opentelemetry-api | via fastapi | Apache-2.0 | <https://pypi.org/project/opentelemetry-api/> |
| pydantic | request validation, via fastapi | MIT | <https://pypi.org/project/pydantic/> |
| pydantic-core | via pydantic | MIT | <https://pypi.org/project/pydantic-core/> |
| annotated-types | via pydantic | MIT | <https://pypi.org/project/annotated-types/> |
| typing-inspection | via pydantic | MIT | <https://pypi.org/project/typing-inspection/> |
| typing-extensions | via fastapi and pydantic | PSF-2.0 | <https://pypi.org/project/typing-extensions/> |
| anyio | via starlette | MIT | <https://pypi.org/project/anyio/> |
| idna | via anyio | BSD-3-Clause | <https://pypi.org/project/idna/> |
| h11 | HTTP/1.1, via uvicorn | MIT | <https://pypi.org/project/h11/> |
| click | via uvicorn | BSD-3-Clause | <https://pypi.org/project/click/> |
| cffi | via cryptography | MIT | <https://pypi.org/project/cffi/> |
| pycparser | via cffi | BSD-3-Clause | <https://pypi.org/project/pycparser/> |

The binary wheels of `cryptography` carry their own copy of OpenSSL, which is under the
Apache-2.0 license. The set of transitive packages can shift a little between releases as the
libraries above change their own dependencies — the versions file described below is the
authoritative list for a given release.

## Why the GPL components do not relicense the panel

openfortivpn, strongSwan, socat, iproute2 and iptables are separate programs that sit side
by side with the panel in the same image. The panel does not link against them and contains
none of their code: it starts them as separate processes and talks to them only through
command lines, configuration files and their output. Shipping independent programs together
like this is what the GPL calls an aggregate ("mere aggregation" in GPL-2.0, section 5 of
GPL-3.0), so their licenses cover those programs and do not extend to the panel's own MIT
code.

Their licenses still apply in full to the programs themselves: you may use, study, change
and redistribute them on their own terms, and you are entitled to their source code — see
below. The Python libraries, which are loaded into the panel's own process, are all under
permissive licenses (MIT, BSD, Apache-2.0, PSF) that sit comfortably next to MIT.

## Exact versions in a release

Every release records the exact versions it was built with:

- in the ZIP package — `THIRD_PARTY_VERSIONS.txt`, next to `start.bat` (along with
  `LICENSE` and `THIRD_PARTY.md`);
- in the image — `/usr/share/doc/tunnelbox/third-party-versions.txt` (with `LICENSE` and
  `THIRD_PARTY.md` beside it in `/usr/share/doc/tunnelbox/`).

To read it straight from an image:

```bash
docker run --rm --entrypoint cat ghcr.io/mysttic/tunnelbox:latest /usr/share/doc/tunnelbox/third-party-versions.txt
```

Put a version number in place of `latest` (e.g. `ghcr.io/mysttic/tunnelbox:3.0.0`) for a
particular release, use `tunnelbox:X.Y.Z` for the image loaded from a ZIP package, or read
it from the running panel with
`docker exec tunnelbox cat /usr/share/doc/tunnelbox/third-party-versions.txt`.

The file has two sections:

- `# Debian packages (binary, version, source)` — one tab-separated line per package: the
  binary package, its exact version and the Debian source package it was built from;
- `# Python packages` — `name==version` for every installed Python distribution
  (`pip freeze --all`).

Every package of the Debian base — not only the ones in the file — can be listed the same
way:

```bash
docker run --rm --entrypoint dpkg-query ghcr.io/mysttic/tunnelbox:latest -W -f '${binary:Package}\t${Version}\t${source:Package}\n'
```

The registry images are built for `linux/amd64`, `linux/arm64` and `linux/arm/v7`, and each
platform's image carries its own file, which is the authoritative one for that platform (add
`--platform linux/arm64` and so on to `docker run` to read another platform's — that runs
the image under emulation, which Docker Desktop provides out of the box). The image inside
the ZIP package is a `linux/amd64` build with a file of its own.

## Getting the source code

- **Debian packages** — <https://snapshot.debian.org/> keeps every source package Debian
  has ever published. Look it up by the source package name and version from the versions
  file: `https://snapshot.debian.org/package/<source>/<version>/`. A binary version ending
  in `+bN` (a rebuild without source changes) comes from the source version without that
  suffix. On a Debian system the same can be fetched with `apt-get source <source>=<version>`
  (with `deb-src` entries enabled) or `debsnap <source> <version>` from `devscripts`.
- **Python packages** — the source distributions (sdists) on PyPI, at
  `https://pypi.org/project/<name>/<version>/#files`, or
  `pip download --no-binary :all: --no-deps <name>==<version>`.
- **Tunnelbox itself** — this repository; the tag `vX.Y.Z` is the exact code of release
  X.Y.Z.

If you cannot obtain the source of a component in a version we shipped, open an issue in
this repository and we will help.
