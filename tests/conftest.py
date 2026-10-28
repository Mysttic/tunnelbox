"""Wspólne fixtures dla testów backendu."""

import pathlib
import sys

import pytest

# udostępnij moduły z katalogu app/
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "app"))


@pytest.fixture
def mowi_po():
    """Przełącza język komunikatów backendu na czas testu i przywraca poprzedni."""
    import i18n
    poprzedni = i18n.current_lang()
    yield i18n.set_lang
    i18n.set_lang(poprzedni)


@pytest.fixture
def main_mod(tmp_path, monkeypatch):
    """Świeży, izolowany moduł aplikacji: pusty sejf i menedżer połączeń per test."""
    import vault as vaultmod
    monkeypatch.setattr(vaultmod, "VAULT_PATH", tmp_path / "vault.enc")

    import connections
    import main
    monkeypatch.setattr(main, "vault", vaultmod.Vault())
    monkeypatch.setattr(main, "manager", connections.ConnectionManager())
    main._session["token"] = None
    return main


@pytest.fixture
def client(main_mod):
    from fastapi.testclient import TestClient
    # panel przyjmuje tylko nazwy tego komputera (ALLOWED_HOSTS) — domyślny
    # „testserver" klienta testowego dostałby 400
    return TestClient(main_mod.app, base_url="http://127.0.0.1")


@pytest.fixture
def auth(client):
    """Tworzy sejf i zwraca nagłówek autoryzacji."""
    r = client.post("/api/vault/create", json={"password": "haslo123"})
    assert r.status_code == 200, r.text
    return {"X-Auth": r.json()["token"]}


def sample_profile(**over):
    p = {
        "name": "Klient",
        "host": "vpn.klient.pl",
        "port": 443,
        "username": "jkowalski",
        "password": "example-password",
        "token_mode": "none",
        "trusted_certs": [],
        "forwards": [{"label": "RDP", "ip": "10.10.10.11", "remote_port": 3389}],
    }
    p.update(over)
    return p
