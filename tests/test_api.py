"""Testy kontraktu API (FastAPI TestClient)."""

import os
import pathlib
import re
import subprocess
import sys

import pytest

from conftest import sample_profile


def test_vault_status_flow(client):
    status = client.get("/api/vault").json()
    assert (status["exists"], status["unlocked"]) == (False, False)
    tok = client.post("/api/vault/create", json={"password": "haslo123"}).json()["token"]
    assert client.get("/api/vault").json()["exists"] is True
    H = {"X-Auth": tok}
    assert client.post("/api/vault/lock", headers=H).json() == {"ok": True}
    assert client.get("/api/state", headers=H).status_code == 401


def test_vault_status_podaje_wersje(client, main_mod):
    """Numer wersji musi być widoczny bez logowania — panel pokazuje go w nagłówku
    także na ekranie hasła głównego."""
    wersja = client.get("/api/vault").json()["version"]
    assert wersja == main_mod.VERSION != "dev"
    plik = (pathlib.Path(main_mod.__file__).resolve().parent.parent / "VERSION")
    assert wersja == plik.read_text(encoding="utf-8").strip()


def test_lock_nie_rozlacza_polaczen(client, auth, main_mod, monkeypatch):
    """Blokada panelu chroni dostęp do konfiguracji, ale tunele mają działać dalej."""
    wywolania = []
    monkeypatch.setattr(main_mod.manager, "disconnect_all",
                        lambda: wywolania.append("disconnect_all"))
    assert client.post("/api/vault/lock", headers=auth).status_code == 200
    assert wywolania == [], "blokada panelu nie może rozłączać aktywnych połączeń"
    # a sam dostęp jest odcięty
    assert client.get("/api/state", headers=auth).status_code == 401


def test_export_import_roundtrip(client, auth):
    import base64 as b64
    client.post("/api/profiles", headers=auth, json=sample_profile(name="Do eksportu"))

    r = client.get("/api/vault/export")
    assert r.status_code == 200
    assert re.fullmatch(r'attachment; filename="tunnelbox-config-\d{4}-\d{2}-\d{2}\.enc"',
                        r.headers["content-disposition"])
    plik = r.content

    # po zablokowaniu import odtwarza konfigurację i od razu loguje
    client.post("/api/vault/lock", headers=auth)
    r2 = client.post("/api/vault/import",
                     json={"data": b64.b64encode(plik).decode(), "password": "haslo123"})
    assert r2.status_code == 200, r2.text
    tok = r2.json()["token"]
    profile = client.get("/api/state", headers={"X-Auth": tok}).json()["profiles"]
    assert profile[0]["name"] == "Do eksportu"


def test_import_eksportu_z_wersji_2_9(client):
    """Eksport z FortiVPN 2.9.x (fortivpn2-konfiguracja-<data>.enc) ma się wczytać bez zmian:
    to jedyna droga przeniesienia zapisanych połączeń do Tunnelboxa. Nazwa pliku do API nie
    trafia (panel wysyła samą zawartość, a sejf rozpoznaje plik po treści), więc liczy się
    tylko format, zbudowany tu ręcznie jak w 2.9.x."""
    import base64 as b64
    import json
    import secrets

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    key = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(b"haslo123")
    dane = {"profiles": [dict(sample_profile(name="Z 2.9"), id="ab12cd34")],
            "settings": {"fast_rdp": False}}
    blob = AESGCM(key).encrypt(nonce, json.dumps(dane).encode(), None)
    plik = json.dumps({k: b64.b64encode(v).decode()
                       for k, v in (("salt", salt), ("nonce", nonce), ("data", blob))})

    r = client.post("/api/vault/import",
                    json={"data": b64.b64encode(plik.encode()).decode(), "password": "haslo123"})
    assert r.status_code == 200, r.text
    stan = client.get("/api/state", headers={"X-Auth": r.json()["token"]}).json()
    assert stan["profiles"][0]["name"] == "Z 2.9"
    assert stan["settings"]["fast_rdp"] is False


def test_import_odrzuca_zle_haslo_i_smieci(client, auth):
    import base64 as b64
    plik = client.get("/api/vault/export").content
    assert client.post("/api/vault/import",
                       json={"data": b64.b64encode(plik).decode(),
                             "password": "nie-to-haslo"}).status_code == 400
    assert client.post("/api/vault/import",
                       json={"data": b64.b64encode(b"to nie jest sejf").decode(),
                             "password": "cokolwiek"}).status_code == 400


def test_import_rozlacza_polaczenia(client, auth, main_mod, monkeypatch):
    """Import zastępuje całą konfigurację — tunele do starych profili muszą paść."""
    import base64 as b64
    plik = client.get("/api/vault/export").content
    wywolania = []
    monkeypatch.setattr(main_mod.manager, "disconnect_all",
                        lambda: wywolania.append("disconnect_all"))
    client.post("/api/vault/import",
                json={"data": b64.b64encode(plik).decode(), "password": "haslo123"})
    assert wywolania == ["disconnect_all"]


def test_export_bez_sejfu_zwraca_404(client):
    assert client.get("/api/vault/export").status_code == 404


def test_change_password_flow(client, auth):
    # zła obecna -> 400
    assert client.post("/api/vault/change-password", headers=auth,
                       json={"current": "bledne", "new": "noweHaslo"}).status_code == 400
    # poprawna zmiana -> 200
    assert client.post("/api/vault/change-password", headers=auth,
                       json={"current": "haslo123", "new": "noweHaslo"}).status_code == 200
    # zablokuj i odblokuj NOWYM hasłem
    client.post("/api/vault/lock", headers=auth)
    assert client.post("/api/vault/unlock", json={"password": "haslo123"}).status_code == 400
    assert client.post("/api/vault/unlock", json={"password": "noweHaslo"}).status_code == 200


def test_change_password_requires_auth(client, auth):
    assert client.post("/api/vault/change-password",
                       json={"current": "haslo123", "new": "noweHaslo"}).status_code == 401


def test_settings_default_and_update(client, auth):
    # domyślnie szybkie łączenie RDP jest włączone
    assert client.get("/api/state", headers=auth).json()["settings"]["fast_rdp"] is True
    # wyłączenie zapisuje się i utrzymuje
    r = client.put("/api/settings", headers=auth, json={"fast_rdp": False})
    assert r.status_code == 200, r.text
    assert r.json()["fast_rdp"] is False
    assert client.get("/api/state", headers=auth).json()["settings"]["fast_rdp"] is False
    # i wraca po ponownym włączeniu
    client.put("/api/settings", headers=auth, json={"fast_rdp": True})
    assert client.get("/api/state", headers=auth).json()["settings"]["fast_rdp"] is True


def test_settings_survive_lock(client, auth):
    client.put("/api/settings", headers=auth, json={"fast_rdp": False})
    client.post("/api/vault/lock", headers=auth)
    tok = client.post("/api/vault/unlock", json={"password": "haslo123"}).json()["token"]
    assert client.get("/api/state", headers={"X-Auth": tok}).json()["settings"]["fast_rdp"] is False


def test_settings_requires_auth(client, auth):
    assert client.put("/api/settings", json={"fast_rdp": False}).status_code == 401


def test_sprawdzanie_aktualizacji_domyslnie_wlaczone(client, auth):
    assert client.get("/api/state", headers=auth).json()["settings"]["check_updates"] is True


def test_update_wymaga_autoryzacji(client, auth):
    assert client.get("/api/update").status_code == 401
    assert client.post("/api/update/check").status_code == 401


def test_update_zwraca_wynik_sprawdzenia(client, auth, main_mod, monkeypatch):
    monkeypatch.setattr(
        main_mod.updates, "check",
        lambda current, force=False: {"current": current, "latest": "9.9.9",
                                      "available": True, "wymuszone": force},
    )
    r = client.get("/api/update", headers=auth).json()
    assert (r["enabled"], r["available"], r["latest"]) == (True, True, "9.9.9")
    assert r["wymuszone"] is False
    # „Sprawdź teraz" pomija pamięć podręczną
    assert client.post("/api/update/check", headers=auth).json()["wymuszone"] is True


@pytest.mark.parametrize("zmienna, oczekiwane", [
    ("", "package"),            # paczka ZIP nie ustawia zmiennej
    ("registry", "registry"),   # docker-compose.yml — obraz z rejestru
    ("source", "source"),       # docker-compose.build.yml — ze źródeł
])
def test_update_podaje_sposob_instalacji(client, auth, main_mod, monkeypatch,
                                         zmienna, oczekiwane):
    """Obrazu z rejestru nie podmieni instalator paczki — panel musi wiedzieć,
    że zamiast przycisku „Zainstaluj" ma podpowiedzieć `docker compose pull`."""
    monkeypatch.setattr(main_mod, "INSTALL", zmienna)
    monkeypatch.setattr(
        main_mod.updates, "check",
        lambda current, force=False: {"current": current, "latest": "9.9.9",
                                      "available": True},
    )
    assert client.get("/api/update", headers=auth).json()["install"] == oczekiwane
    assert client.post("/api/update/check", headers=auth).json()["install"] == oczekiwane
    # stan jest wczytany zawsze przed przyciskami RDP — tam też musi być
    assert client.get("/api/state", headers=auth).json()["install"] == oczekiwane


@pytest.mark.parametrize("zmienna", ["", "registry"])
def test_sposob_instalacji_takze_przy_wylaczonym_sprawdzaniu(client, auth, main_mod,
                                                             monkeypatch, zmienna):
    monkeypatch.setattr(main_mod, "INSTALL", zmienna)
    client.put("/api/settings", headers=auth,
               json={"fast_rdp": True, "check_updates": False})
    r = client.get("/api/update", headers=auth).json()
    assert r["enabled"] is False
    assert r["install"] == (zmienna or "package")
    assert client.post("/api/update/check", headers=auth).json()["install"] == r["install"]


@pytest.mark.parametrize("zmienna, oczekiwane", [("registry", "registry"), (None, "")])
def test_sposob_instalacji_czytany_ze_zmiennej_srodowiskowej(zmienna, oczekiwane):
    """TUNNELBOX_INSTALL ustawia plik compose — panel czyta ją raz, przy starcie.
    Osobny proces, bo moduł czyta zmienną przy imporcie."""
    env = {k: v for k, v in os.environ.items() if k != "TUNNELBOX_INSTALL"}
    if zmienna is not None:
        env["TUNNELBOX_INSTALL"] = zmienna
    env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parent.parent / "app")
    wynik = subprocess.run([sys.executable, "-c", "import main; print(repr(main.INSTALL))"],
                           env=env, capture_output=True, text=True, timeout=60)
    assert wynik.returncode == 0, wynik.stderr
    assert wynik.stdout.strip() == repr(oczekiwane)


def test_update_wylaczony_nie_wychodzi_do_sieci(client, auth, main_mod, monkeypatch):
    """Wyłączone sprawdzanie ma znaczyć: panel nie łączy się z niczym poza VPN-em."""
    monkeypatch.setattr(
        main_mod.updates, "check",
        lambda *a, **k: pytest.fail("nie wolno pytać, gdy sprawdzanie jest wyłączone"),
    )
    client.put("/api/settings", headers=auth,
               json={"fast_rdp": True, "check_updates": False})
    r = client.get("/api/update", headers=auth).json()
    assert r["enabled"] is False
    assert r["available"] is False
    assert r["current"] == main_mod.VERSION


def test_auth_required(client, auth):
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers={"X-Auth": "zly-token"}).status_code == 401
    assert client.get("/api/state", headers=auth).status_code == 200


def test_require_auth_non_ascii_header(main_mod):
    # regresja: nagłówek spoza ASCII nie może rzucać TypeError -> 500
    from fastapi import HTTPException
    main_mod.vault.create("haslo123")
    main_mod._session["token"] = "abc123def456"
    with pytest.raises(HTTPException) as exc:
        main_mod._require_auth("café")
    assert exc.value.status_code == 401


def test_create_profile_autoport(client, auth):
    r = client.post("/api/profiles", headers=auth, json=sample_profile())
    assert r.status_code == 200, r.text
    lp = r.json()["forwards"][0]["local_port"]
    assert 13391 <= lp <= 13449


def test_unique_ports_across_profiles(client, auth):
    a = client.post("/api/profiles", headers=auth, json=sample_profile(name="A")).json()
    b = client.post("/api/profiles", headers=auth, json=sample_profile(name="B")).json()
    assert a["forwards"][0]["local_port"] != b["forwards"][0]["local_port"]


def test_explicit_local_port_collision(client, auth):
    p1 = sample_profile(name="A", forwards=[{"ip": "10.0.0.1", "remote_port": 3389, "local_port": 13400}])
    assert client.post("/api/profiles", headers=auth, json=p1).status_code == 200
    p2 = sample_profile(name="B", forwards=[{"ip": "10.0.0.2", "remote_port": 22, "local_port": 13400}])
    assert client.post("/api/profiles", headers=auth, json=p2).status_code == 400


@pytest.mark.parametrize("bad", [
    {"forwards": [{"ip": "", "remote_port": 22}]},          # puste IP
    {"host": "ma spacje"},                                    # spacja w host
    {"password": "kończy spacją "},                           # spacja końcowa hasła
    {"username": "nowa\nlinia"},                              # znak nowej linii
    {"trusted_certs": ["xyz"]},                               # zły cert
    {"forwards": [{"ip": "1.2.3.4", "remote_port": 99999}]},  # port poza zakresem
    {"token_mode": "cokolwiek"},                              # zły tryb tokena
])
def test_validation_rejects(client, auth, bad):
    assert client.post("/api/profiles", headers=auth, json=sample_profile(**bad)).status_code == 422


def test_token_push_connect_without_otp(client, auth):
    pid = client.post("/api/profiles", headers=auth,
                      json=sample_profile(token_mode="push")).json()["id"]
    r = client.post(f"/api/profiles/{pid}/connect", headers=auth, json={})
    assert r.status_code == 200, r.text
    client.post(f"/api/profiles/{pid}/disconnect", headers=auth)


def test_token_code_connect_without_otp_rejected(client, auth):
    pid = client.post("/api/profiles", headers=auth,
                      json=sample_profile(token_mode="code")).json()["id"]
    assert client.post(f"/api/profiles/{pid}/connect", headers=auth, json={}).status_code == 400


def test_connect_none_ok(client, auth):
    pid = client.post("/api/profiles", headers=auth,
                      json=sample_profile(token_mode="none")).json()["id"]
    assert client.post(f"/api/profiles/{pid}/connect", headers=auth, json={}).status_code == 200
    client.post(f"/api/profiles/{pid}/disconnect", headers=auth)


def test_trust_without_pending_cert(client, auth):
    pid = client.post("/api/profiles", headers=auth, json=sample_profile()).json()["id"]
    assert client.post(f"/api/profiles/{pid}/trust", headers=auth).status_code == 409


def test_add_forward_to_disconnected(client, auth):
    pid = client.post("/api/profiles", headers=auth, json=sample_profile()).json()["id"]
    r = client.post(f"/api/profiles/{pid}/forwards", headers=auth,
                    json={"label": "SSH", "ip": "10.0.0.9", "remote_port": 22})
    assert r.status_code == 200, r.text
    assert 13391 <= r.json()["local_port"] <= 13449
    profiles = client.get("/api/state", headers=auth).json()["profiles"]
    assert len(profiles[0]["forwards"]) == 2


def test_add_forward_port_collision(client, auth):
    a = client.post("/api/profiles", headers=auth, json=sample_profile(name="A")).json()
    taken = a["forwards"][0]["local_port"]
    b = client.post("/api/profiles", headers=auth, json=sample_profile(name="B")).json()
    r = client.post(f"/api/profiles/{b['id']}/forwards", headers=auth,
                    json={"ip": "10.0.0.9", "remote_port": 22, "local_port": taken})
    assert r.status_code == 400


def test_add_forward_validation(client, auth):
    pid = client.post("/api/profiles", headers=auth, json=sample_profile()).json()["id"]
    assert client.post(f"/api/profiles/{pid}/forwards", headers=auth,
                       json={"ip": "", "remote_port": 22}).status_code == 422


def test_add_forward_unknown_profile(client, auth):
    assert client.post("/api/profiles/nieistnieje/forwards", headers=auth,
                       json={"ip": "10.0.0.9", "remote_port": 22}).status_code == 404


def test_delete_profile(client, auth):
    pid = client.post("/api/profiles", headers=auth, json=sample_profile()).json()["id"]
    assert client.delete(f"/api/profiles/{pid}", headers=auth).status_code == 200
    assert client.get("/api/state", headers=auth).json()["profiles"] == []


def test_realm_accepted_and_stored(client, auth):
    r = client.post("/api/profiles", headers=auth,
                    json=sample_profile(host="vpn.klient.pl", realm="myrealm"))
    assert r.status_code == 200, r.text
    assert r.json()["realm"] == "myrealm"


def test_realm_strips_slashes(client, auth):
    r = client.post("/api/profiles", headers=auth,
                    json=sample_profile(name="Z", realm="/myrealm/"))
    assert r.json()["realm"] == "myrealm"


def test_requires_token_derived_from_mode(client, auth):
    r = client.post("/api/profiles", headers=auth, json=sample_profile(token_mode="push"))
    assert r.json()["requires_token"] is True
    r2 = client.post("/api/profiles", headers=auth, json=sample_profile(name="Z", token_mode="none"))
    assert r2.json()["requires_token"] is False


# --- profile IPsec ---

def ipsec_profile(**over):
    p = sample_profile(name="Klient IPsec", vpn_type="ipsec",
                       ipsec_psk="KluczWspoldzielony")
    p.update(over)
    return p


def test_ipsec_profil_zapisuje_wszystkie_pola(client, auth):
    r = client.post("/api/profiles", headers=auth, json=ipsec_profile(
        ipsec_auth="ikev1-psk-xauth", ipsec_local_id="grupa-vpn",
        ipsec_remote_id="brama.klient.pl", ipsec_remote_ts="10.10.0.0/16, 192.168.5.0/24",
        ipsec_aggressive=True))
    assert r.status_code == 200, r.text
    zapisany = r.json()
    assert zapisany["vpn_type"] == "ipsec"
    assert zapisany["ipsec_psk"] == "KluczWspoldzielony"
    assert zapisany["ipsec_local_id"] == "grupa-vpn"
    assert zapisany["ipsec_aggressive"] is True
    # lista sieci jest normalizowana przy zapisie
    assert zapisany["ipsec_remote_ts"] == "10.10.0.0/16,192.168.5.0/24"


def test_ipsec_bez_klucza_odrzucony(client, auth):
    assert client.post("/api/profiles", headers=auth,
                       json=ipsec_profile(ipsec_psk="")).status_code == 422


def test_ipsec_nie_obsluguje_tokena_push(client, auth):
    # push to mechanizm FortiClienta po SSL-VPN — przy IPsec nie ma go jak zrealizować
    assert client.post("/api/profiles", headers=auth,
                       json=ipsec_profile(token_mode="push")).status_code == 422


def test_ipsec_na_sam_psk_nie_wymaga_loginu(client, auth):
    r = client.post("/api/profiles", headers=auth, json=ipsec_profile(
        ipsec_auth="ikev2-psk", username="", password=""))
    assert r.status_code == 200, r.text
    assert r.json()["username"] == ""


def test_ipsec_na_sam_psk_odrzuca_token(client, auth):
    # nie ma pola hasła, do którego można by dokleić kod
    assert client.post("/api/profiles", headers=auth, json=ipsec_profile(
        ipsec_auth="ikev2-psk", username="", password="",
        token_mode="code")).status_code == 422


def test_ssl_nadal_wymaga_loginu_i_hasla(client, auth):
    assert client.post("/api/profiles", headers=auth,
                       json=sample_profile(username="")).status_code == 422
    assert client.post("/api/profiles", headers=auth,
                       json=sample_profile(password="")).status_code == 422


@pytest.mark.parametrize("bad", [
    {"vpn_type": "wireguard"},                    # nieznany typ tunelu
    {"ipsec_auth": "ikev9-magia"},                # nieznany tryb uwierzytelniania
    {"ipsec_remote_ts": "nie-jest-siecia"},       # śmieci w liście sieci
    {"ipsec_local_id": "ma spacje"},              # niedozwolone znaki w identyfikatorze
    {"ipsec_psk": "klucz\nz nową linią"},         # znak sterujący w kluczu
])
def test_ipsec_walidacja_odrzuca(client, auth, bad):
    assert client.post("/api/profiles", headers=auth,
                       json=ipsec_profile(**bad)).status_code == 422


def test_profil_bez_typu_to_nadal_ssl(client, auth):
    """Sejfy sprzed IPsec nie mają pola vpn_type — muszą działać bez zmian."""
    r = client.post("/api/profiles", headers=auth, json=sample_profile())
    assert r.status_code == 200, r.text
    assert r.json()["vpn_type"] == "ssl"


def test_ipsec_connect_z_tokenem_wymaga_kodu(client, auth):
    pid = client.post("/api/profiles", headers=auth,
                      json=ipsec_profile(token_mode="code")).json()["id"]
    assert client.post(f"/api/profiles/{pid}/connect", headers=auth,
                       json={}).status_code == 400
    r = client.post(f"/api/profiles/{pid}/connect", headers=auth, json={"otp": "123456"})
    assert r.status_code == 200, r.text
    client.post(f"/api/profiles/{pid}/disconnect", headers=auth)


# --- nagłówek Host (DNS rebinding) ---

@pytest.mark.parametrize("host", [
    "127.0.0.1:25263",          # skrypty startowe i instalator aktualizacji
    "tunnelbox.localhost:25263",
    "panel.localhost:25263",    # każda nazwa *.localhost to ten komputer
    "localhost:25263",
])
def test_panel_odpowiada_pod_nazwami_tego_komputera(client, host):
    r = client.get("/api/vault", headers={"Host": host})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("sciezka", ["/api/vault", "/api/vault/export", "/"])
def test_obca_domena_dostaje_400(client, auth, sciezka):
    """Strona z internetu może przepiąć swoją domenę na 127.0.0.1 (DNS rebinding)
    i wołać API jako „ta sama strona". Eksport sejfu działa bez sesji, więc bez
    sprawdzenia nagłówka Host dałoby się nim wynieść zaszyfrowany sejf."""
    r = client.get(sciezka, headers={"Host": "evil.example:25263"})
    assert (r.status_code, r.text) == (400, "Invalid host header")


def test_import_z_obcej_domeny_nie_podmienia_konfiguracji(client, auth, main_mod):
    przed = main_mod.vault.export_bytes()
    r = client.post("/api/vault/import", headers={"Host": "evil.example"},
                    json={"data": "AAAA", "password": "x"})
    assert (r.status_code, r.text) == (400, "Invalid host header")
    assert main_mod.vault.export_bytes() == przed
