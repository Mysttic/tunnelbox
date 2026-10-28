"""Testy logiki połączeń niezależnej od sieci (tryby tokena, generowanie configu)."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "app"))

from connections import (  # noqa: E402
    LOCAL_PORT_MAX,
    LOCAL_PORT_MIN,
    ConnectionManager,
    local_host,
    token_mode,
)


def test_local_host_unikalny_dla_kazdego_portu():
    # Każdy port lokalny musi mieć własny adres — Windows zapisuje poświadczenia
    # RDP pod kluczem TERMSRV/<adres> bez portu, więc wspólny adres oznaczałby
    # nadpisywanie haseł między maszynami.
    ports = range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1)
    hosts = [local_host(p) for p in ports]
    assert len(set(hosts)) == len(hosts)


def test_local_host_zakres_i_przypisanie():
    assert local_host(LOCAL_PORT_MIN) == "127.0.0.2"
    assert local_host(LOCAL_PORT_MIN + 1) == "127.0.0.3"
    assert local_host(LOCAL_PORT_MAX) == "127.0.0.60"
    # musi zostać w pętli zwrotnej i nie kolidować z 127.0.0.1 ani adresem rozgłoszeniowym
    for p in range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1):
        last = int(local_host(p).rsplit(".", 1)[1])
        assert 2 <= last <= 254


def test_token_mode_explicit():
    assert token_mode({"token_mode": "none"}) == "none"
    assert token_mode({"token_mode": "code"}) == "code"
    assert token_mode({"token_mode": "push"}) == "push"


def test_token_mode_legacy():
    # stary format profilu bez token_mode
    assert token_mode({"requires_token": True}) == "code"
    assert token_mode({"requires_token": False}) == "none"
    assert token_mode({}) == "none"


def _write(tmp_path, profile, otp=None):
    path = tmp_path / "vpn.conf"
    ConnectionManager._write_vpn_config(str(path), profile, otp)
    return path.read_text()


def test_config_code_with_otp(tmp_path):
    cfg = _write(tmp_path, {"host": "h", "username": "u", "password": "p",
                            "token_mode": "code"}, otp="123456")
    assert "no-ftm-push = 1" in cfg
    assert "otp = 123456" in cfg


def test_config_push_has_no_ftm_disable(tmp_path):
    # push: NIE wolno wyłączać ftm-push ani podawać otp
    cfg = _write(tmp_path, {"host": "h", "username": "u", "password": "p",
                            "token_mode": "push"}, otp=None)
    assert "no-ftm-push" not in cfg
    assert "otp" not in cfg


def test_config_none(tmp_path):
    cfg = _write(tmp_path, {"host": "h", "username": "u", "password": "p",
                            "token_mode": "none"})
    assert "no-ftm-push" not in cfg
    assert "otp" not in cfg


def test_add_forward_live_starts_forward():
    """Dokładanie maszyny do połączonego tunelu uruchamia nowe przekierowanie."""
    from connections import Connection
    mgr = ConnectionManager()
    conn = Connection("p1", 1)
    conn.state = "connected"
    mgr._connections["p1"] = conn
    started = []
    mgr._start_forward = lambda c, f: started.append((c.ns, f["local_port"]))

    mgr.add_forward_live("p1", {"ip": "10.0.0.5", "remote_port": 22, "local_port": 13399})
    assert started == [("vpn1", 13399)]


def test_add_forward_live_requires_connected():
    from connections import Connection, ConnectionError_
    import pytest as _pytest
    mgr = ConnectionManager()
    conn = Connection("p1", 1)
    conn.state = "connecting"          # jeszcze nie połączone
    mgr._connections["p1"] = conn
    with _pytest.raises(ConnectionError_):
        mgr.add_forward_live("p1", {"ip": "10.0.0.5", "remote_port": 22, "local_port": 13399})
    with _pytest.raises(ConnectionError_):
        mgr.add_forward_live("nieznane", {"ip": "10.0.0.5", "remote_port": 22, "local_port": 13399})


def test_add_forward_live_rejects_duplicate_port():
    from connections import Connection, ConnectionError_
    import pytest as _pytest
    mgr = ConnectionManager()
    conn = Connection("p1", 1)
    conn.state = "connected"
    conn.forwards.append({"local_port": 13399, "procs": []})
    mgr._connections["p1"] = conn
    with _pytest.raises(ConnectionError_):
        mgr.add_forward_live("p1", {"ip": "10.0.0.5", "remote_port": 22, "local_port": 13399})


def test_config_realm(tmp_path):
    cfg = _write(tmp_path, {"host": "vpn.klient.pl", "username": "u", "password": "p",
                            "realm": "myrealm"})
    assert "realm = myrealm" in cfg


def test_config_no_realm_when_empty(tmp_path):
    cfg = _write(tmp_path, {"host": "h", "username": "u", "password": "p", "realm": ""})
    assert "realm" not in cfg


def test_config_basic_fields_and_certs(tmp_path):
    cfg = _write(tmp_path, {"host": "10.0.0.1", "port": 10443, "username": "u",
                            "password": "sekret", "trusted_certs": ["aa11", "bb22"]})
    assert "host = 10.0.0.1" in cfg
    assert "port = 10443" in cfg
    assert "set-dns = 0" in cfg
    assert "trusted-cert = aa11" in cfg
    assert "trusted-cert = bb22" in cfg


import pytest  # noqa: E402


@pytest.mark.skipif(sys.platform == "win32", reason="uprawnienia POSIX (0600) — sprawdzane na Linuksie/CI")
def test_config_file_permissions(tmp_path):
    import os
    path = tmp_path / "vpn.conf"
    ConnectionManager._write_vpn_config(str(path), {"host": "h", "username": "u",
                                                    "password": "p"}, None)
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600


def test_vpn_type_domyslnie_ssl():
    from connections import vpn_type
    # profile zapisane przed wprowadzeniem IPsec nie mają tego pola
    assert vpn_type({}) == "ssl"
    assert vpn_type({"vpn_type": "ssl"}) == "ssl"
    assert vpn_type({"vpn_type": "cokolwiek"}) == "ssl"
    assert vpn_type({"vpn_type": "ipsec"}) == "ipsec"
