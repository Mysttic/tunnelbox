"""Tunele IPsec (strongSwan) — budowa konfiguracji demona i sterowanie nim przez swanctl.

Moduł zna wyłącznie strongSwana: przygotowuje katalog konfiguracji dla JEDNEJ instancji
demona i rozmawia z nią gniazdem vici. Cyklem życia połączenia (netns, przekierowania
portów, stan pokazywany w panelu) zarządza `connections.py`.

Decyzje, które warto znać przy czytaniu:
  - jedna instancja demona na tunel — polityki XFRM, trasy i gniazda IKE należą do
    przestrzeni sieciowej, więc demon musi działać wewnątrz netns połączenia,
  - `charon-systemd`, a nie `charon` — ten drugi pilnuje pliku PID w stałej ścieżce
    (/var/run/charon.pid) i odmawia startu, gdy działa już inna instancja; wariant
    "systemd" trzyma się pierwszego planu i loguje na stderr, czyli dokładnie tak,
    jak panel czyta openfortivpn,
  - katalog konfiguracji (0700) leży POZA netns: `ip netns exec` podmienia tylko pliki
    z /etc, więc swanctl uruchomiony w głównej przestrzeni trafia gniazdem vici do
    właściwego demona — nie trzeba wchodzić do netns przy każdej komendzie,
  - tryby uwierzytelniania ograniczone do wariantów bez certyfikatów: FortiGate w
    dial-upie przedstawia zwykle certyfikat self-signed, którego i tak nie dałoby się
    zweryfikować bez ręcznego wgrania CA klienta.
"""

import os
import re
import subprocess
import time

from i18n import t

CHARON_BIN = "/usr/sbin/charon-systemd"
SWANCTL_BIN = "/usr/sbin/swanctl"

# Katalogi robocze tuneli. /run jest wspólne dla całego kontenera (netns nie izoluje
# systemu plików), więc gniazdo vici jest widoczne z głównej przestrzeni sieciowej.
RUNTIME_ROOT = "/run/tunnelbox-ipsec"

# Nazwa połączenia i dziecka (child SA) w swanctl.conf — jedna na instancję demona,
# więc może być stała.
CONN_NAME = "fvpn"

# Tryby uwierzytelniania. Wartość niesie też wersję IKE, żeby nie trzymać dwóch pól,
# które mogą sobie zaprzeczyć.
AUTH_MODES = ("ikev1-psk-xauth", "ikev1-psk", "ikev2-psk")
DEFAULT_AUTH = AUTH_MODES[0]

# Tryby, w których brama pyta dodatkowo o login i hasło użytkownika.
USER_AUTH_MODES = ("ikev1-psk-xauth",)

# Domyślny zakres sieci po drugiej stronie tunelu. 0.0.0.0/0 = "wszystko przez VPN";
# ruch i tak żyje w osobnym netns, więc nie zabiera internetu reszcie kontenera.
DEFAULT_REMOTE_TS = "0.0.0.0/0"

# Zestaw propozycji obejmuje domyślne szyfry FortiGate (AES-128/256 + SHA-1/SHA-256,
# DH 2/5/14) i kończy się słowem `default`, czyli współczesnym zestawem strongSwana.
IKE_PROPOSALS = (
    "aes256-sha256-modp2048,aes256-sha256-modp1536,aes128-sha256-modp1536,"
    "aes256-sha1-modp1536,aes128-sha1-modp1536,aes256-sha256-modp1024,"
    "aes128-sha1-modp1024,default"
)
ESP_PROPOSALS = "aes256-sha256,aes128-sha256,aes256-sha1,aes128-sha1,default"

VICI_WAIT_SECONDS = 20      # ile czekamy, aż demon otworzy gniazdo sterujące
INITIATE_TIMEOUT = 75       # ile czekamy na zestawienie tunelu (IKE + child SA)
WATCH_INTERVAL = 20         # co ile sekund pilnujemy, czy tunel jeszcze stoi
WATCH_MISSES = 3            # tyle nieudanych sprawdzeń z rzędu = tunel zerwany

# Adres/podsieć w zapisie CIDR — jedyne, co wpuszczamy do pola "sieci za VPN-em".
_CIDR_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$")

# charon melduje przy starcie KAŻDĄ opcjonalną wtyczkę, której nie ma w obrazie
# (ldap, pkcs11, curl...). Dla użytkownika to kilkanaście linii szumu, więc nie
# trafiają do logu w panelu.
_NOISE_RE = re.compile(r"failed to load - \w+_plugin_create not found")

# Retransmisja = brama nie odpowiedziała na naszą pierwszą wiadomość IKE.
_RETRANSMIT_RE = re.compile(r"retransmit \d+ of request")

# Rozpoznawanie przyczyn awarii w logu charona. Kolejność ma znaczenie — pierwszy
# trafiony wzorzec wygrywa, a szczegółowe komunikaty stoją przed ogólnymi.
# W tabeli są klucze komunikatów, nie gotowe teksty — panel mówi po polsku albo
# po angielsku, zależnie od ustawienia.
_DIAGNOSTICS = (
    (re.compile(r"XAuth authentication .*failed|EAP method .* failed|"
                r"AUTHENTICATION_FAILED|authentication of .* failed", re.I),
     "ipsec.authRejected"),
    (re.compile(r"no shared key found|no matching peer config|"
                r"no peer config found", re.I),
     "ipsec.badPsk"),
    (re.compile(r"NO_PROPOSAL_CHOSEN|no acceptable proposal", re.I),
     "ipsec.noProposal"),
    (re.compile(r"TS_UNACCEPTABLE|no acceptable traffic selectors", re.I),
     "ipsec.badTs"),
    (re.compile(r"INVALID_ID_INFORMATION|INVALID_KE_PAYLOAD", re.I),
     "ipsec.badParams"),
    (re.compile(r"peer not responding|retransmit .* timed out|giving up after|"
                r"unable to resolve|no route to host|network is unreachable|"
                r"destination address required", re.I),
     "ipsec.unreachable"),
    (re.compile(r"unable to (create|install) (policy|SA)|"
                r"failed to (add|install) SAD entry", re.I),
     "ipsec.kernelRejected"),
)


# --- odczyt profilu ---

def auth_mode(profile: dict) -> str:
    mode = profile.get("ipsec_auth")
    return mode if mode in AUTH_MODES else DEFAULT_AUTH


def ike_version(mode: str) -> int:
    return 1 if mode.startswith("ikev1") else 2


def uses_user_auth(mode: str) -> bool:
    """Czy tryb wymaga loginu i hasła (poza kluczem PSK)."""
    return mode in USER_AUTH_MODES


def remote_ts(profile: dict) -> str:
    """Sieci po drugiej stronie tunelu, w formacie listy dla swanctl."""
    raw = (profile.get("ipsec_remote_ts") or "").strip()
    if not raw:
        return DEFAULT_REMOTE_TS
    nets = [n.strip() for n in raw.replace(";", ",").split(",") if n.strip()]
    nets = [n for n in nets if _CIDR_RE.match(n)]
    return ",".join(nets) if nets else DEFAULT_REMOTE_TS


# --- ścieżki ---

def config_dir(ns: str) -> str:
    return f"{RUNTIME_ROOT}/{ns}"


def vici_socket(cfg_dir: str) -> str:
    return f"{cfg_dir}/charon.vici"


# --- konfiguracja ---

def _quote(value) -> str:
    """Wartość w cudzysłowie, zgodnie ze składnią strongswan.conf/swanctl.conf."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped + '"'


def _write_private(path: str, text: str):
    """Zapis pliku widocznego tylko dla roota — w środku są hasła i klucz PSK.

    Kodowanie wymuszamy na UTF-8: hasło albo klucz PSK bywa z polskimi znakami,
    a domyślne kodowanie zależy od ustawień lokalnych procesu.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def daemon_conf(cfg_dir: str, aggressive: bool = False) -> str:
    """strongswan.conf dla jednej instancji demona.

    Zaczyna się od konfiguracji dystrybucyjnej (listy wtyczek w /etc/strongswan.d),
    a dokłada tylko to, co musi być per połączenie: własne gniazdo vici i własny plik
    dla wtyczki `resolve`, żeby demon nie nadpisał resolv.conf przestrzeni sieciowej
    (DNS ustawia tam connections.py).

    `aggressive` odblokowuje tryb agresywny z kluczem PSK. strongSwan domyślnie go
    odmawia, bo hasz PSK leci wtedy otwartym tekstem i da się go łamać offline —
    stąd ostentacyjna nazwa opcji. Włączamy ją wyłącznie wtedy, gdy użytkownik sam
    zaznaczył tryb agresywny, bo część bram FortiGate inaczej nie przyjmie klienta.
    """
    resolv = f"{cfg_dir}/resolv.conf"
    return (
        "# Wygenerowane automatycznie przez Tunnelbox - nie edytuj recznie.\n"
        "include /etc/strongswan.d/*.conf\n"
        "\n"
        "charon {\n"
        "  load_modular = yes\n"
        "  install_routes = yes\n"
        "  install_virtual_ip = yes\n"
        + ("  i_dont_care_about_security_and_use_aggressive_mode_psk = yes\n"
           if aggressive else "")
        + "  # log na stderr - panel czyta go tak samo jak wyjscie openfortivpn\n"
        "  filelog {\n"
        "    stderr {\n"
        "      default = 1\n"
        "      ike = 2\n"
        "      cfg = 1\n"
        "      time_format = %H:%M:%S\n"
        "    }\n"
        "  }\n"
        "  plugins {\n"
        "    include /etc/strongswan.d/charon/*.conf\n"
        "    vici {\n"
        f"      socket = unix://{vici_socket(cfg_dir)}\n"
        "    }\n"
        "    resolve {\n"
        f"      file = {resolv}\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


def swanctl_conf(profile: dict, otp: str | None = None) -> str:
    """swanctl.conf: definicja połączenia + sekrety.

    Kod tokena doklejamy do hasła — tak FortiGate przyjmuje FortiToken przy XAuth
    (pole hasła zawiera hasło i kod jeden po drugim).
    """
    mode = auth_mode(profile)
    version = ike_version(mode)
    user = str(profile.get("username") or "")
    secret = str(profile.get("password") or "")
    if otp and uses_user_auth(mode):
        secret += otp
    psk = str(profile.get("ipsec_psk") or "")
    local_id = str(profile.get("ipsec_local_id") or "").strip()
    remote_id = str(profile.get("ipsec_remote_id") or "").strip()
    aggressive = bool(profile.get("ipsec_aggressive")) and version == 1

    rounds = ["    local-psk {\n      auth = psk\n"
              + (f"      id = {_quote(local_id)}\n" if local_id else "")
              + "    }\n"]
    secrets = ["  ike-" + CONN_NAME + " {\n"
               f"    secret = {_quote(psk)}\n"
               "  }\n"]
    if uses_user_auth(mode):
        rounds.append("    local-xauth {\n      auth = xauth\n"
                      f"      xauth_id = {_quote(user)}\n"
                      "    }\n")
        secrets.append("  xauth-" + CONN_NAME + " {\n"
                       f"    id = {_quote(user)}\n"
                       f"    secret = {_quote(secret)}\n"
                       "  }\n")
    rounds.append("    remote-gw {\n      auth = psk\n"
                  + (f"      id = {_quote(remote_id)}\n" if remote_id else "")
                  + "    }\n")

    return (
        "# Wygenerowane automatycznie przez Tunnelbox - nie edytuj recznie.\n"
        "connections {\n"
        f"  {CONN_NAME} {{\n"
        f"    version = {version}\n"
        f"    remote_addrs = {profile['host']}\n"
        "    local_addrs = %any\n"
        "    # prosimy brame o adres w sieci klienta (mode config / config payload)\n"
        "    vips = 0.0.0.0\n"
        f"    proposals = {IKE_PROPOSALS}\n"
        "    # ruch i tak przechodzi przez MASQUERADE kontenera, wiec NAT-T jest pewny\n"
        "    encap = yes\n"
        "    fragmentation = yes\n"
        "    dpd_delay = 30s\n"
        f"    aggressive = {'yes' if aggressive else 'no'}\n"
        + "".join(rounds) +
        "    children {\n"
        f"      {CONN_NAME} {{\n"
        f"        remote_ts = {remote_ts(profile)}\n"
        "        local_ts = dynamic\n"
        f"        esp_proposals = {ESP_PROPOSALS}\n"
        "        dpd_action = restart\n"
        "        close_action = restart\n"
        "        start_action = none\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
        "\n"
        "secrets {\n"
        + "".join(secrets) +
        "}\n"
    )


def write_config(cfg_dir: str, profile: dict, otp: str | None = None) -> str:
    """Tworzy katalog konfiguracji jednego tunelu i zwraca jego ścieżkę."""
    swanctl_dir = f"{cfg_dir}/swanctl"
    os.makedirs(swanctl_dir, exist_ok=True)
    os.chmod(cfg_dir, 0o700)
    aggressive = (bool(profile.get("ipsec_aggressive"))
                  and ike_version(auth_mode(profile)) == 1)
    _write_private(f"{cfg_dir}/strongswan.conf", daemon_conf(cfg_dir, aggressive))
    _write_private(f"{swanctl_dir}/swanctl.conf", swanctl_conf(profile, otp))
    return cfg_dir


# --- uruchamianie i sterowanie ---

def daemon_command(ns: str) -> list:
    return ["ip", "netns", "exec", ns, "stdbuf", "-oL", "-eL", CHARON_BIN]


def daemon_env(cfg_dir: str) -> dict:
    env = dict(os.environ)
    env["STRONGSWAN_CONF"] = f"{cfg_dir}/strongswan.conf"
    env["SWANCTL_DIR"] = f"{cfg_dir}/swanctl"
    return env


def swanctl(cfg_dir: str, args: list, timeout: float = 30):
    """Uruchamia swanctl przeciwko demonowi tego połączenia.

    `args` musi zaczynać się od komendy (np. --load-all) — swanctl przyjmuje `--uri`
    dopiero jako opcję komendy, więc doklejamy je na końcu.
    """
    cmd = [SWANCTL_BIN] + args + ["--uri", "unix://" + vici_socket(cfg_dir)]
    return subprocess.run(cmd, env=daemon_env(cfg_dir), capture_output=True,
                          text=True, errors="replace", timeout=timeout)


def wait_for_vici(cfg_dir: str, alive=None, timeout: float = VICI_WAIT_SECONDS) -> bool:
    """Czeka, aż demon otworzy gniazdo sterujące. `alive` przerywa, gdy proces padł."""
    deadline = time.monotonic() + timeout
    socket_path = vici_socket(cfg_dir)
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            return True
        if alive is not None and not alive():
            return False
        time.sleep(0.2)
    return os.path.exists(socket_path)


def child_installed(cfg_dir: str) -> bool:
    """Czy tunel (child SA) jest zestawiony."""
    try:
        result = swanctl(cfg_dir, ["--list-sas"], timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "INSTALLED" in (result.stdout or "")


def xfrm_available(ns: str | None = None) -> bool:
    """Czy jądro udostępnia IPsec (XFRM). Bez tego nie ma o czym rozmawiać."""
    cmd = (["ip", "netns", "exec", ns] if ns else []) + ["ip", "xfrm", "policy"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def timeout_reason(log_lines) -> str:
    """Komunikat dla tunelu, który nie wstał w wyznaczonym czasie.

    Retransmisje w logu znaczą, że brama w ogóle się nie odezwała — to zupełnie inna
    porada niż „coś poszło nie tak". Sprawdzamy je dopiero tutaj, a nie w `explain()`,
    bo pojedyncza zgubiona paczka na zdrowym łączu też wywołuje retransmisję i nie
    powinna zasłaniać późniejszego, właściwego błędu.
    """
    if any(_RETRANSMIT_RE.search(line) for line in list(log_lines)[-60:]):
        return t("ipsec.gatewaySilent")
    return t("ipsec.timeout")


def is_noise(line: str) -> bool:
    """Czy linia logu jest szumem startowym demona, którego nie warto pokazywać."""
    return bool(_NOISE_RE.search(line))


def explain(line: str) -> str | None:
    """Tłumaczy linię logu charona na komunikat dla użytkownika (albo None)."""
    for pattern, key in _DIAGNOSTICS:
        if pattern.search(line):
            return t(key)
    return None
