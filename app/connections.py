"""Zarządzanie tunelami VPN — Forti SSL-VPN (openfortivpn) oraz IPsec (strongSwan).

Każde aktywne połączenie dostaje własną przestrzeń sieciową (netns) w kontenerze,
dzięki czemu kilka sieci klientów o tych samych adresach IP nie koliduje ze sobą.

Typ tunelu wybiera profil (pole `vpn_type`); różni się tylko sposób jego zestawienia:
  - SSL-VPN: openfortivpn wypisuje postęp na stdout, więc czytamy jego log,
  - IPsec:   demon charon działa w tle, a stan zestawiamy i sprawdzamy przez swanctl
             (szczegóły w `ipsec.py`).
Wszystko po zestawieniu tunelu — przekierowania portów, diagnostyka, sprzątanie —
jest wspólne.

Schemat pojedynczego połączenia (index = i):
  netns "vpn<i>"  <-- veth ns_ip --- root_ip veth -->  główny netns
  - klient VPN działa wewnątrz netns (interfejs tunelu i trasy VPN żyją tylko tam),
  - ruch do bramy VPN wychodzi przez veth + MASQUERADE na świat,
  - podsieć transferowa to /30 z TEST-NET-3 (203.0.113.0/24, RFC 5737) — adres
    zarezerwowany na dokumentację, nieobecny w LAN klienta i wśród adresów PPP
    FortiGate, więc brama nie wepchnie kolidującej trasy (link-local 169.254.x
    kolidował: FortiGate używa 169.254.2.1 jako peera PPP),
  - każde przekierowanie portu to para socat:
      główny netns:  TCP-LISTEN:<port>  ->  <ns_ip>:<port>
      netns:         TCP-LISTEN:<port>  ->  <host_zdalny>:<port_zdalny>  (przez ppp0)
"""

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque

import ipsec
from i18n import t

LOCAL_PORT_MIN = 13391
LOCAL_PORT_MAX = 13449  # musi pokrywać się z zakresem portów w docker-compose.yml

# Na hoście każdy port lokalny jest publikowany na własnym adresie pętli zwrotnej
# (13391 -> 127.0.0.2, 13392 -> 127.0.0.3, ...). Wewnątrz kontenera socat nasłuchuje
# normalnie na wszystkich interfejsach — ten podział istnieje wyłącznie po stronie
# hosta, bo Windows zapisuje poświadczenia RDP pod kluczem TERMSRV/<adres> BEZ portu.
LOOPBACK_FIRST = 2


def local_host(local_port: int) -> str:
    """Adres pętli zwrotnej, pod którym host widzi dane przekierowanie."""
    return f"127.0.0.{local_port - LOCAL_PORT_MIN + LOOPBACK_FIRST}"

TUNNEL_UP_RE = re.compile(r"Tunnel is up and running")
TRUSTED_CERT_RE = re.compile(r"--trusted-cert\s+([0-9a-fA-F]{32,})")
AUTH_FAIL_RE = re.compile(r"Could not authenticate|Access denied|Login failed", re.I)
NET_FAIL_RE = re.compile(
    r"Could not connect|gethostbyname|getaddrinfo|Connection refused|"
    r"Connection timed out|timed out|No route to host|Network is unreachable",
    re.I,
)
PPP_FAIL_RE = re.compile(r"/dev/ppp|Cannot open .*ppp|pppd", re.I)

ACTIVE_STATES = {"connecting", "connected", "disconnecting"}
KILL_GRACE_SECONDS = 10


def vpn_type(profile: dict) -> str:
    """Zwraca typ tunelu: 'ssl' (Forti SSL-VPN) albo 'ipsec'.

    Profile zapisane przed wprowadzeniem IPsec nie mają tego pola — to zawsze SSL-VPN.
    """
    return "ipsec" if profile.get("vpn_type") == "ipsec" else "ssl"


def token_mode(profile: dict) -> str:
    """Zwraca tryb tokena: 'none' | 'code' | 'push'.

    Wspiera stary format profilu (pole requires_token) — brak token_mode oznacza
    'code', jeśli requires_token było prawdą.
    """
    mode = profile.get("token_mode")
    if mode in ("none", "code", "push"):
        return mode
    return "code" if profile.get("requires_token") else "none"


class ConnectionError_(Exception):
    """Błąd zestawiania tunelu. `code` pozwala panelowi rozpoznać konkretny przypadek
    bez czytania treści komunikatu — ta zależy od wybranego języka."""

    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


class Connection:
    def __init__(self, profile_id: str, index: int):
        self.profile_id = profile_id
        self.index = index
        self.ns = f"vpn{index}"
        # Podsieć transferowa /30 z TEST-NET-3 (203.0.113.0/24, RFC 5737 — zarezerwowana
        # na dokumentację). Nie występuje w LAN klienta ani jako adres peera PPP FortiGate,
        # więc brama nie wepchnie kolidującej trasy (link-local 169.254.x powodował kolizję:
        # FortiGate używa 169.254.2.1 jako peera PPP).
        base = 4 * index               # bloki: index 1 -> .4/30, index 2 -> .8/30, ...
        self.net30 = f"203.0.113.{base}/30"
        self.root_ip = f"203.0.113.{base + 1}"   # koniec w głównym netns (veth_root)
        self.ns_ip = f"203.0.113.{base + 2}"     # koniec w netns połączenia (veth_ns)
        self.state = "connecting"
        self.detail = ""
        self.pending_cert = None
        self.stop_requested = False
        self.log = deque(maxlen=300)
        self.vpn_proc = None
        self.forwards = []  # [{local_port, ip, remote_port, label, procs:[...]}]


class ConnectionManager:
    def __init__(self):
        self._connections = {}  # profile_id -> Connection
        self._used_indexes = set()
        self._lock = threading.Lock()
        self._prepare_container()

    # --- API ---

    def connect(self, profile: dict, otp: str | None):
        with self._lock:
            existing = self._connections.get(profile["id"])
            if existing and existing.state in ACTIVE_STATES:
                raise ConnectionError_(t("conn.alreadyActive"), code="already_active")
            # index 1..62 -> bloki /30 w 203.0.113.0/24 (ns_ip do .250)
            index = next((i for i in range(1, 63) if i not in self._used_indexes), None)
            if index is None:
                raise ConnectionError_(t("conn.tooMany"))
            self._used_indexes.add(index)
            conn = Connection(profile["id"], index)
            self._connections[profile["id"]] = conn
        threading.Thread(target=self._run, args=(conn, profile, otp), daemon=True).start()

    def disconnect(self, profile_id: str):
        with self._lock:
            conn = self._connections.get(profile_id)
            if not conn or conn.state not in ACTIVE_STATES:
                return
            conn.stop_requested = True
            conn.state = "disconnecting"
            proc = conn.vpn_proc
        if proc and proc.poll() is None:
            proc.terminate()
            threading.Timer(KILL_GRACE_SECONDS, self._force_kill, args=(proc,)).start()

    def disconnect_all(self):
        for pid in list(self._connections):
            self.disconnect(pid)

    def is_active(self, profile_id: str) -> bool:
        with self._lock:
            conn = self._connections.get(profile_id)
            return bool(conn and conn.state in ACTIVE_STATES)

    def reset(self, profile_id: str):
        """Kasuje nieaktywny wpis połączenia (np. po edycji profilu w stanie need_trust)."""
        with self._lock:
            conn = self._connections.get(profile_id)
            if conn and conn.state not in ACTIVE_STATES:
                del self._connections[profile_id]

    def take_pending_cert(self, profile_id: str) -> str | None:
        with self._lock:
            conn = self._connections.get(profile_id)
            if conn and conn.state == "need_trust" and conn.pending_cert:
                cert = conn.pending_cert
                conn.pending_cert = None
                conn.state = "disconnected"
                return cert
        return None

    def status(self) -> dict:
        out = {}
        with self._lock:
            for pid, conn in self._connections.items():
                out[pid] = {
                    "state": conn.state,
                    "detail": conn.detail,
                    "pending_cert": conn.pending_cert if conn.state == "need_trust" else None,
                    "log": list(conn.log)[-60:],
                    "forwards": [
                        {
                            "local_port": f["local_port"],
                            "alive": all(p.poll() is None for p in f["procs"]),
                        }
                        for f in conn.forwards
                    ],
                }
        return out

    # --- cykl życia połączenia ---

    def _run(self, conn: Connection, profile: dict, otp: str | None):
        """Cały cykl życia połączenia — blokuje aż do rozłączenia albo awarii.

        Zestawienie tunelu zależy od typu (`_run_ssl` / `_run_ipsec`), reszta jest
        wspólna: przestrzeń sieciowa, ustalenie stanu końcowego i sprzątanie.
        """
        final_state, final_detail = "error", ""
        connected_seen = False
        try:
            self._setup_netns(conn)
            with self._lock:
                if conn.stop_requested:
                    final_state, final_detail = "disconnected", ""
                    return
            if vpn_type(profile) == "ipsec":
                connected_seen = self._run_ipsec(conn, profile, otp)
            else:
                connected_seen = self._run_ssl(conn, profile, otp)

            if conn.stop_requested:
                final_state, final_detail = "disconnected", ""
            elif conn.pending_cert:
                final_state = "need_trust"
                final_detail = t("conn.unknownCert")
            elif connected_seen:
                final_state = "error"
                final_detail = conn.detail or t("conn.dropped")
            else:
                final_state = "error"
                final_detail = conn.detail or t("conn.failed")
        except Exception as e:
            final_state = "error"
            final_detail = conn.detail or t("conn.internal", error=e)
        finally:
            self._cleanup(conn)
            with self._lock:
                conn.state = final_state
                conn.detail = final_detail
                self._used_indexes.discard(conn.index)

    def _run_ssl(self, conn: Connection, profile: dict, otp: str | None) -> bool:
        """Tunel Forti SSL-VPN. Zwraca True, jeśli udało się dojść do stanu połączonego.

        openfortivpn relacjonuje postęp na stdout, więc jedna pętla czyta log,
        rozpoznaje w nim błędy i wyłapuje moment wstania tunelu.
        """
        cfg_path = f"/tmp/vpn_{conn.profile_id}.conf"
        connected_seen = False
        try:
            self._write_vpn_config(cfg_path, profile, otp)

            with self._lock:
                if conn.stop_requested:
                    return False
                conn.vpn_proc = subprocess.Popen(
                    ["ip", "netns", "exec", conn.ns, "stdbuf", "-oL", "-eL",
                     "openfortivpn", "-c", cfg_path],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors="replace", start_new_session=True,
                )

            for line in conn.vpn_proc.stdout:
                line = line.rstrip()
                if line:
                    conn.log.append(line)
                m = TRUSTED_CERT_RE.search(line)
                if m:
                    conn.pending_cert = m.group(1)
                if conn.state == "connecting" and not conn.detail:
                    if AUTH_FAIL_RE.search(line):
                        conn.detail = t("conn.authRejected")
                    elif NET_FAIL_RE.search(line):
                        conn.detail = t("conn.unreachable")
                    elif PPP_FAIL_RE.search(line):
                        conn.detail = t("conn.noPpp")
                if (TUNNEL_UP_RE.search(line) and conn.state == "connecting"
                        and not conn.stop_requested):
                    try:
                        self._log_diagnostics(conn, profile)
                        self._start_forwards(conn, profile)
                        conn.state = "connected"
                        conn.detail = ""
                        connected_seen = True
                    except Exception as e:
                        conn.detail = t("conn.forwardsFailed", error=e)
                        conn.vpn_proc.terminate()

            conn.vpn_proc.wait()
            return connected_seen
        finally:
            try:
                os.remove(cfg_path)
            except OSError:
                pass

    def _run_ipsec(self, conn: Connection, profile: dict, otp: str | None) -> bool:
        """Tunel IPsec. Zwraca True, jeśli udało się dojść do stanu połączonego.

        charon nie relacjonuje postępu tak jak openfortivpn — log leci osobnym wątkiem,
        a o zestawienie tunelu prosimy wprost przez swanctl i sprawdzamy wynik.
        """
        cfg_dir = ipsec.config_dir(conn.ns)
        if not ipsec.xfrm_available(conn.ns):
            conn.detail = t("conn.noXfrm")
            return False
        ipsec.write_config(cfg_dir, profile, otp)

        with self._lock:
            if conn.stop_requested:
                return False
            conn.vpn_proc = subprocess.Popen(
                ipsec.daemon_command(conn.ns), env=ipsec.daemon_env(cfg_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", start_new_session=True,
            )
        proc = conn.vpn_proc
        pump = threading.Thread(target=self._pump_ipsec_log, args=(conn, proc), daemon=True)
        pump.start()

        connected = False
        try:
            self._ipsec_up(conn, profile, cfg_dir)
            connected = True
        except ConnectionError_ as e:
            conn.detail = conn.detail or str(e)
        except Exception as e:
            conn.detail = conn.detail or t("conn.ipsecFailed", error=e)

        if connected:
            threading.Thread(target=self._watch_ipsec, args=(conn, proc, cfg_dir),
                             daemon=True).start()
        else:
            _kill_group(proc)

        proc.wait()
        pump.join(timeout=5)
        return connected

    def _ipsec_up(self, conn: Connection, profile: dict, cfg_dir: str):
        """Wczytuje konfigurację do demona, zestawia tunel i uruchamia przekierowania."""
        proc = conn.vpn_proc
        if not ipsec.wait_for_vici(cfg_dir, alive=lambda: proc.poll() is None):
            raise ConnectionError_(t("conn.daemonFailed"))

        result = ipsec.swanctl(cfg_dir, ["--load-all"])
        if result.returncode != 0:
            self._log_swanctl(conn, result)
            raise ConnectionError_(t("conn.configFailed"))

        conn.log.append(t("conn.configLoaded"))
        result = ipsec.swanctl(
            cfg_dir,
            ["--initiate", "--child", ipsec.CONN_NAME, "--timeout", str(ipsec.INITIATE_TIMEOUT)],
            timeout=ipsec.INITIATE_TIMEOUT + 20,
        )
        self._log_swanctl(conn, result)
        if conn.stop_requested:
            raise ConnectionError_(t("conn.aborted"))
        # swanctl zwraca błąd także wtedy, gdy tunel wstał tuż po upływie limitu —
        # ostatnie słowo ma faktyczny stan SA, nie kod wyjścia.
        if result.returncode != 0 and not ipsec.child_installed(cfg_dir):
            raise ConnectionError_(conn.detail or ipsec.timeout_reason(conn.log))

        self._log_diagnostics(conn, profile)
        try:
            self._start_forwards(conn, profile)
        except Exception as e:
            raise ConnectionError_(t("conn.forwardsFailed", error=e))
        conn.state = "connected"
        conn.detail = ""

    def _pump_ipsec_log(self, conn: Connection, proc):
        """Przepisuje log charona do panelu i tłumaczy z niego przyczynę awarii."""
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line or ipsec.is_noise(line):
                    continue
                conn.log.append(line)
                if conn.state == "connecting" and not conn.detail:
                    why = ipsec.explain(line)
                    if why:
                        conn.detail = why
        except Exception:
            pass

    def _watch_ipsec(self, conn: Connection, proc, cfg_dir: str):
        """Pilnuje, czy tunel nadal stoi.

        charon sam próbuje odtworzyć zerwane SA (dpd_action/close_action = restart),
        więc dajemy mu na to kilka cykli; dopiero potem gasimy demona, żeby panel
        pokazał zerwane połączenie zamiast kłamać, że wszystko działa.
        """
        misses = 0
        while proc.poll() is None and not conn.stop_requested:
            time.sleep(ipsec.WATCH_INTERVAL)
            if proc.poll() is not None or conn.stop_requested:
                return
            if ipsec.child_installed(cfg_dir):
                misses = 0
                continue
            misses += 1
            conn.log.append(t("conn.saMissing", misses=misses, total=ipsec.WATCH_MISSES))
            if misses >= ipsec.WATCH_MISSES:
                conn.detail = t("conn.ipsecDropped")
                _kill_group(proc)
                return

    @staticmethod
    def _log_swanctl(conn: Connection, result):
        for stream in (result.stdout, result.stderr):
            for line in (stream or "").splitlines():
                if line.strip() and not ipsec.is_noise(line):
                    conn.log.append(f"swanctl: {line.rstrip()}")

    def _setup_netns(self, conn: Connection):
        ns, i = conn.ns, conn.index
        veth_root, veth_ns = f"veth{i}r", f"veth{i}n"
        # sprzątanie po ewentualnych pozostałościach
        _run_quiet(["ip", "netns", "del", ns])
        _run_quiet(["ip", "link", "del", veth_root])

        _run(["ip", "netns", "add", ns])
        _run(["ip", "link", "add", veth_root, "type", "veth", "peer", "name", veth_ns])
        _run(["ip", "link", "set", veth_ns, "netns", ns])
        _run(["ip", "addr", "add", f"{conn.root_ip}/30", "dev", veth_root])
        _run(["ip", "link", "set", veth_root, "up"])
        _run(["ip", "netns", "exec", ns, "ip", "addr", "add", f"{conn.ns_ip}/30", "dev", veth_ns])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", veth_ns, "up"])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"])
        _run(["ip", "netns", "exec", ns, "ip", "route", "add", "default", "via", conn.root_ip])

        # utwardzenie routingu: wyłącz reverse-path filtering na obu końcach veth
        # (ruch netns<->MASQUERADE jest asymetryczny) i wymuś forwarding po stronie roota
        _run_quiet(["sysctl", "-w", f"net.ipv4.conf.{veth_root}.rp_filter=0"])
        _run_quiet(["sysctl", "-w", f"net.ipv4.conf.{veth_root}.forwarding=1"])
        _run_quiet(["ip", "netns", "exec", ns, "sysctl", "-w", "net.ipv4.conf.all.rp_filter=0"])
        _run_quiet(["ip", "netns", "exec", ns, "sysctl", "-w", f"net.ipv4.conf.{veth_ns}.rp_filter=0"])

        # DNS w netns: wbudowany DNS Dockera (127.0.0.11) jest tam niedostępny
        os.makedirs(f"/etc/netns/{ns}", exist_ok=True)
        with open(f"/etc/netns/{ns}/resolv.conf", "w") as f:
            f.write("nameserver 1.1.1.1\nnameserver 8.8.8.8\n")

        _run(["iptables", "-t", "nat", "-A", "POSTROUTING",
              "-s", conn.net30, "-j", "MASQUERADE"])

    def add_forward_live(self, profile_id: str, fwd: dict):
        """Dokłada przekierowanie do DZIAŁAJĄCEGO połączenia (bez rozłączania)."""
        with self._lock:
            conn = self._connections.get(profile_id)
            if not conn or conn.state != "connected":
                raise ConnectionError_(t("conn.notActive"))
            if any(f["local_port"] == fwd["local_port"] for f in conn.forwards):
                raise ConnectionError_(
                    t("conn.portInUse", port=fwd["local_port"]))
        self._start_forward(conn, fwd)

    def _start_forwards(self, conn: Connection, profile: dict):
        for fwd in profile.get("forwards", []):
            self._start_forward(conn, fwd)

    def _start_forward(self, conn: Connection, fwd: dict):
        """Uruchamia parę socat dla jednego przekierowania i weryfikuje start."""
        local_port = fwd["local_port"]
        entry = {
            "local_port": local_port,
            "ip": fwd["ip"],
            "remote_port": fwd["remote_port"],
            "label": fwd.get("label") or fwd["ip"],
            "procs": [],
        }
        inner = ["ip", "netns", "exec", conn.ns, "socat",
                 f"TCP-LISTEN:{local_port},fork,reuseaddr",
                 f"TCP:{fwd['ip']}:{fwd['remote_port']}"]
        outer = ["socat",
                 f"TCP-LISTEN:{local_port},fork,reuseaddr",
                 f"TCP:{conn.ns_ip}:{local_port}"]
        for cmd in (inner, outer):
            proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, errors="replace", start_new_session=True,
            )
            entry["procs"].append(proc)
            threading.Thread(
                target=self._drain_stderr, args=(conn, proc, local_port), daemon=True
            ).start()
        with self._lock:  # śledź wpis zanim sprawdzisz — cleanup musi go objąć
            conn.forwards.append(entry)

        # daj socatowi chwilę i sprawdź, czy nie padł od razu (zajęty port, złe IP)
        time.sleep(0.3)
        for proc in entry["procs"]:
            if proc.poll() is not None:
                raise ConnectionError_(
                    t("conn.forwardFailed", port=local_port, code=proc.returncode)
                )
        conn.log.append(
            f"Przekierowanie: {local_host(local_port)}:{local_port} -> "
            f"{fwd['ip']}:{fwd['remote_port']} ({entry['label']})"
        )

    @staticmethod
    def _drain_stderr(conn: Connection, proc, local_port: int):
        try:
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    conn.log.append(f"socat[{local_port}]: {line}")
        except Exception:
            pass

    def _cleanup(self, conn: Connection):
        for entry in conn.forwards:
            for proc in entry["procs"]:
                _kill_group(proc)
        conn.forwards = []
        _run_quiet(["iptables", "-t", "nat", "-D", "POSTROUTING",
                    "-s", conn.net30, "-j", "MASQUERADE"])
        _run_quiet(["ip", "netns", "del", conn.ns])
        _run_quiet(["ip", "link", "del", f"veth{conn.index}r"])
        shutil.rmtree(f"/etc/netns/{conn.ns}", ignore_errors=True)
        # katalog IPsec trzyma hasło i klucz PSK — kasujemy go razem z tunelem
        shutil.rmtree(ipsec.config_dir(conn.ns), ignore_errors=True)

    @staticmethod
    def _force_kill(proc):
        if proc.poll() is None:
            _kill_group(proc, signal.SIGKILL)

    @staticmethod
    def _write_vpn_config(path: str, profile: dict, otp: str | None):
        lines = [
            f"host = {profile['host']}",
            f"port = {profile.get('port', 443)}",
            f"username = {profile['username']}",
            f"password = {profile['password']}",
            "set-dns = 0",
        ]
        realm = (profile.get("realm") or "").strip().strip("/")
        if realm:
            lines.append(f"realm = {realm}")
        mode = token_mode(profile)
        if mode == "code":
            # kod jednorazowy wpisywany ręcznie — wyłącz push, podaj kod
            lines.append("no-ftm-push = 1")
            if otp:
                lines.append(f"otp = {otp}")
        # mode == "push": nic nie dodajemy — openfortivpn wyśle push do aplikacji
        # i poczeka na zatwierdzenie na telefonie (domyślne zachowanie FTM).
        # mode == "none": bez tokena.
        for cert in profile.get("trusted_certs", []):
            lines.append(f"trusted-cert = {cert}")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")

    def _log_diagnostics(self, conn: Connection, profile: dict):
        """Zapisuje do logu trasowanie w tunelu — pomaga diagnozować brak łączności."""
        conn.log.append(t("conn.diagStart"))
        r = subprocess.run(["ip", "netns", "exec", conn.ns, "ip", "route"],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            conn.log.append(t("conn.route", line=line))
        if vpn_type(profile) == "ipsec":
            # IPsec nie tworzy interfejsu z trasami — ruch kieruje polityka XFRM
            # i osobna tablica tras, więc bez tego diagnostyka nic by nie mówiła.
            for label, cmd in (
                ("SA", ["ip", "netns", "exec", conn.ns, "ip", "-s", "xfrm", "state", "count"]),
                ("polityka", ["ip", "netns", "exec", conn.ns, "ip", "xfrm", "policy"]),
                ("tablica 220", ["ip", "netns", "exec", conn.ns, "ip", "route",
                                 "show", "table", "220"]),
                ("adresy", ["ip", "netns", "exec", conn.ns, "ip", "-o", "addr", "show"]),
            ):
                out = subprocess.run(cmd, capture_output=True, text=True)
                for line in out.stdout.splitlines():
                    conn.log.append(f"{label}: {line.strip()}")
        for fwd in profile.get("forwards", []):
            g = subprocess.run(
                ["ip", "netns", "exec", conn.ns, "ip", "route", "get", fwd["ip"]],
                capture_output=True, text=True,
            )
            first = (g.stdout.strip().splitlines() or [g.stderr.strip()])[0]
            conn.log.append(t("conn.routeTo", ip=fwd["ip"], line=first))
        conn.log.append(t("conn.diagEnd"))

    @staticmethod
    def _prepare_container():
        # ip_forward: przekazywanie ruchu netns <-> internet (MASQUERADE).
        # rp_filter=0: routing jest asymetryczny (netns -> veth -> MASQUERADE),
        # więc strict reverse-path filtering odrzucałby ruch powrotny.
        for key in ("net.ipv4.ip_forward=1",
                    "net.ipv4.conf.all.rp_filter=0",
                    "net.ipv4.conf.default.rp_filter=0"):
            _run_quiet(["sysctl", "-w", key])


def _kill_group(proc, sig=signal.SIGTERM):
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _run(cmd: list):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise ConnectionError_(t("conn.missingTool", tool=cmd[0]))
    if result.returncode != 0:
        raise ConnectionError_(f"{' '.join(cmd)}: {result.stderr.strip()}")


def _run_quiet(cmd: list):
    try:
        subprocess.run(cmd, capture_output=True)
    except FileNotFoundError:
        pass
