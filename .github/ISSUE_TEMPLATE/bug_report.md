---
name: Bug report
about: Something in Tunnelbox does not work the way the manual describes
title: ''
labels: bug
---

<!--
Never paste passwords, one-time codes, pre-shared keys, certificates or your vault
password here, neither in the text nor in attached files or screenshots.
You can write in English or Polish.
-->

### Version

<!-- The panel shows its version in the header, next to the name (e.g. v3.0.0). -->

### Environment

- Operating system (e.g. Windows 11 23H2, macOS 15, Ubuntu 24.04):
- Docker Desktop or Docker Engine version (`docker version`):

### Install method

- [ ] Registry (`docker compose` with `ghcr.io/mysttic/tunnelbox` / Docker Hub)
- [ ] ZIP package (`tunnelbox-X.Y.Z.zip`, `start.bat` / `start.sh`)
- [ ] From source (`git clone`, root `start.sh` / `start.ps1`)

### Connection type

- [ ] SSL-VPN (FortiGate, openfortivpn)
- [ ] IPsec (strongSwan)

### Steps to reproduce

1.
2.
3.

### Expected behaviour

### Actual behaviour

### Diagnostics

With the affected tunnel(s) connected, run:

```
docker exec tunnelbox /diagnose.sh > diag.txt
```

and attach `diag.txt`. **Review it before attaching**: it lists the addresses, routes and
target machines of your tunnels, so it contains internal IP addresses and hostnames of your
networks — remove anything you do not want to share publicly.

### Connection log

<!--
On the connection's card click "Show connection log" and paste the relevant part here.
Check it for internal addresses, hostnames and user names you do not want to share.
-->

```
paste the log here
```
