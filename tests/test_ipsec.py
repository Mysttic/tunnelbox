"""Testy budowy konfiguracji IPsec i tłumaczenia logu strongSwana."""

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "app"))

import i18n
import ipsec  # noqa: E402


def profil(**over):
    p = {
        "host": "vpn.klient.pl",
        "username": "jkowalski",
        "password": "example-password",
        "ipsec_psk": "KluczWspoldzielony",
        "ipsec_auth": "ikev1-psk-xauth",
    }
    p.update(over)
    return p


# --- odczyt profilu ---

def test_auth_mode_domyslny_i_nieznany():
    assert ipsec.auth_mode({}) == "ikev1-psk-xauth"
    assert ipsec.auth_mode({"ipsec_auth": "cokolwiek"}) == "ikev1-psk-xauth"
    assert ipsec.auth_mode({"ipsec_auth": "ikev2-psk"}) == "ikev2-psk"


def test_ike_version_wynika_z_trybu():
    assert ipsec.ike_version("ikev1-psk-xauth") == 1
    assert ipsec.ike_version("ikev1-psk") == 1
    assert ipsec.ike_version("ikev2-psk") == 2


def test_tylko_xauth_pyta_o_uzytkownika():
    assert ipsec.uses_user_auth("ikev1-psk-xauth") is True
    assert ipsec.uses_user_auth("ikev1-psk") is False
    assert ipsec.uses_user_auth("ikev2-psk") is False


def test_remote_ts_puste_to_caly_ruch():
    assert ipsec.remote_ts({}) == "0.0.0.0/0"
    assert ipsec.remote_ts({"ipsec_remote_ts": "   "}) == "0.0.0.0/0"


def test_remote_ts_lista_i_odsiew_smieci():
    assert ipsec.remote_ts({"ipsec_remote_ts": "10.0.0.0/8, 192.168.1.0/24"}) == \
        "10.0.0.0/8,192.168.1.0/24"
    # średnik też jest separatorem, a wpisy bez sensu nie mogą trafić do konfiguracji
    assert ipsec.remote_ts({"ipsec_remote_ts": "10.0.0.0/8; nie-siec"}) == "10.0.0.0/8"
    assert ipsec.remote_ts({"ipsec_remote_ts": "sama-bzdura"}) == "0.0.0.0/0"


# --- swanctl.conf ---

def test_xauth_dodaje_runde_i_sekret():
    cfg = ipsec.swanctl_conf(profil())
    assert "version = 1" in cfg
    assert "local-xauth {" in cfg
    assert 'xauth_id = "jkowalski"' in cfg
    assert "xauth-fvpn {" in cfg
    assert 'secret = "example-password"' in cfg
    assert 'secret = "KluczWspoldzielony"' in cfg


def test_tryb_na_sam_psk_nie_wysyla_loginu():
    cfg = ipsec.swanctl_conf(profil(ipsec_auth="ikev2-psk"))
    assert "version = 2" in cfg
    assert "xauth" not in cfg
    assert "jkowalski" not in cfg
    assert "example-password" not in cfg


def test_token_doklejany_do_hasla_tylko_przy_uwierzytelnianiu_uzytkownika():
    # FortiGate przy XAuth przyjmuje FortiToken jako hasło+kod w jednym polu
    cfg = ipsec.swanctl_conf(profil(), otp="654321")
    assert 'secret = "example-password654321"' in cfg
    # tryb na sam PSK nie ma gdzie wysłać kodu — klucz musi zostać nietknięty
    cfg2 = ipsec.swanctl_conf(profil(ipsec_auth="ikev2-psk"), otp="654321")
    assert "654321" not in cfg2


def test_tryb_agresywny_tylko_dla_ikev1():
    assert "aggressive = yes" in ipsec.swanctl_conf(profil(ipsec_aggressive=True))
    # IKEv2 nie zna trybu agresywnego — nie wolno go tam wpisać
    assert "aggressive = no" in ipsec.swanctl_conf(
        profil(ipsec_auth="ikev2-psk", ipsec_aggressive=True))
    assert "aggressive = no" in ipsec.swanctl_conf(profil())


def test_identyfikatory_tylko_gdy_podane():
    cfg = ipsec.swanctl_conf(profil())
    # samodzielna linia "id =" (xauth_id nie liczy się jako identyfikator IKE)
    assert "\n      id = " not in cfg.split("secrets {")[0]
    cfg2 = ipsec.swanctl_conf(profil(ipsec_local_id="grupa", ipsec_remote_id="brama.pl"))
    assert 'id = "grupa"' in cfg2
    assert 'id = "brama.pl"' in cfg2


def test_wartosci_sa_cytowane_i_escapowane():
    # cudzysłów w haśle nie może rozwalić składni pliku
    cfg = ipsec.swanctl_conf(profil(password='ha"slo\\x', ipsec_psk='kl"ucz'))
    assert 'secret = "ha\\"slo\\\\x"' in cfg
    assert 'secret = "kl\\"ucz"' in cfg


def test_konfiguracja_zawiera_host_i_sieci():
    cfg = ipsec.swanctl_conf(profil(host="10.1.2.3", ipsec_remote_ts="172.16.0.0/12"))
    assert "remote_addrs = 10.1.2.3" in cfg
    assert "remote_ts = 172.16.0.0/12" in cfg
    assert "local_ts = dynamic" in cfg
    assert "vips = 0.0.0.0" in cfg


# --- strongswan.conf ---

def test_daemon_conf_ma_wlasne_gniazdo_i_nie_rusza_resolv_conf():
    cfg = ipsec.daemon_conf("/run/tunnelbox-ipsec/vpn3")
    assert "socket = unix:///run/tunnelbox-ipsec/vpn3/charon.vici" in cfg
    assert "file = /run/tunnelbox-ipsec/vpn3/resolv.conf" in cfg
    assert "include /etc/strongswan.d/*.conf" in cfg
    assert "install_routes = yes" in cfg


def test_wygenerowane_pliki_maja_naglowek():
    """Ktoś, kto zajrzy do /run w kontenerze, ma wiedzieć, skąd te pliki są."""
    naglowek = "# Wygenerowane automatycznie przez Tunnelbox - nie edytuj recznie.\n"
    assert ipsec.daemon_conf("/run/x").startswith(naglowek)
    assert ipsec.swanctl_conf(profil()).startswith(naglowek)


def test_kazde_polaczenie_ma_wlasny_katalog():
    assert ipsec.config_dir("vpn1") != ipsec.config_dir("vpn2")
    assert ipsec.config_dir("vpn1") == "/run/tunnelbox-ipsec/vpn1"
    assert ipsec.vici_socket(ipsec.config_dir("vpn1")).endswith("vpn1/charon.vici")


def test_swanctl_dostaje_uri_po_komendzie(monkeypatch):
    """swanctl 5.9 przyjmuje --uri dopiero jako opcję komendy, nie przed nią."""
    zapamietane = {}
    monkeypatch.setattr(ipsec.subprocess, "run",
                        lambda cmd, **kw: zapamietane.setdefault("cmd", cmd))
    ipsec.swanctl("/run/x", ["--load-all"])
    cmd = zapamietane["cmd"]
    assert cmd[1] == "--load-all"
    assert cmd[-2:] == ["--uri", "unix:///run/x/charon.vici"]


def test_write_config_tworzy_pliki(tmp_path):
    cfg_dir = str(tmp_path / "vpn1")
    ipsec.write_config(cfg_dir, profil())
    assert os.path.exists(os.path.join(cfg_dir, "strongswan.conf"))
    assert os.path.exists(os.path.join(cfg_dir, "swanctl", "swanctl.conf"))


@pytest.mark.skipif(sys.platform == "win32",
                    reason="uprawnienia POSIX (0600) — sprawdzane na Linuksie/CI")
def test_pliki_z_sekretami_tylko_dla_roota(tmp_path):
    cfg_dir = str(tmp_path / "vpn1")
    ipsec.write_config(cfg_dir, profil())
    for path in (os.path.join(cfg_dir, "strongswan.conf"),
                 os.path.join(cfg_dir, "swanctl", "swanctl.conf")):
        assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(cfg_dir).st_mode & 0o777 == 0o700


# --- czytanie logu ---

@pytest.mark.parametrize("jezyk", ["en", "pl"])
@pytest.mark.parametrize("linia, klucz", [
    ("06[IKE] XAuth authentication of 'jkowalski' (myself) failed", "ipsec.authRejected"),
    ("06[ENC] received AUTHENTICATION_FAILED notify error", "ipsec.authRejected"),
    ("06[IKE] no shared key found for 'x' - 'y'", "ipsec.badPsk"),
    ("06[IKE] received NO_PROPOSAL_CHOSEN error notify", "ipsec.noProposal"),
    ("06[IKE] received TS_UNACCEPTABLE notify", "ipsec.badTs"),
    ("06[IKE] establishing IKE_SA failed, peer not responding", "ipsec.unreachable"),
])
def test_explain_tlumaczy_znane_bledy(linia, klucz, jezyk, mowi_po):
    """Log charona ma zamieniać się w poradę — w języku wybranym w panelu."""
    mowi_po(jezyk)
    assert ipsec.explain(linia) == i18n.MESSAGES[jezyk][klucz]


def test_explain_milczy_przy_zwyklym_logu():
    assert ipsec.explain("06[NET] sending packet: from 1.2.3.4[500] to 5.6.7.8[500]") is None


def test_szum_startowy_nie_trafia_do_panelu():
    assert ipsec.is_noise("plugin 'curl': failed to load - curl_plugin_create not found")
    assert not ipsec.is_noise("06[IKE] CHILD_SA fvpn{1} established")


@pytest.mark.parametrize("jezyk", ["en", "pl"])
def test_timeout_rozpoznaje_milczaca_brame(jezyk, mowi_po):
    mowi_po(jezyk)
    log = ["06[IKE] initiating Main Mode", "06[IKE] sending retransmit 3 of request message ID 0"]
    assert ipsec.timeout_reason(log) == i18n.MESSAGES[jezyk]["ipsec.gatewaySilent"]
    assert ipsec.timeout_reason(["06[IKE] coś tam"]) == i18n.MESSAGES[jezyk]["ipsec.timeout"]


def test_tryb_agresywny_odblokowuje_psk_w_demonie(tmp_path):
    """strongSwan odmawia trybu agresywnego z PSK, dopóki nie włączy się tej opcji."""
    flaga = "i_dont_care_about_security_and_use_aggressive_mode_psk = yes"
    # domyślnie nie osłabiamy demona
    assert flaga not in ipsec.daemon_conf("/run/x")
    assert flaga in ipsec.daemon_conf("/run/x", aggressive=True)

    cfg_dir = str(tmp_path / "vpn1")
    ipsec.write_config(cfg_dir, profil(ipsec_aggressive=True))
    assert flaga in open(cfg_dir + "/strongswan.conf", encoding="utf-8").read()

    # IKEv2 nie zna trybu agresywnego — opcja nie ma prawa się tam pojawić
    cfg_dir2 = str(tmp_path / "vpn2")
    ipsec.write_config(cfg_dir2, profil(ipsec_auth="ikev2-psk", ipsec_aggressive=True))
    assert flaga not in open(cfg_dir2 + "/strongswan.conf", encoding="utf-8").read()
