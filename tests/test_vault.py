"""Testy sejfu (szyfrowanie profili)."""

import pytest


@pytest.fixture
def vault(tmp_path, monkeypatch):
    import vault as vaultmod
    monkeypatch.setattr(vaultmod, "VAULT_PATH", tmp_path / "vault.enc")
    return vaultmod.Vault()


def test_create_unlock_roundtrip(vault):
    from vault import Vault, VAULT_PATH  # noqa: F401
    assert not vault.exists
    vault.create("haslo123")
    assert vault.exists and vault.unlocked
    p = vault.add_profile({"name": "X", "host": "h", "forwards": []})
    pid = p["id"]
    vault.lock()
    assert not vault.unlocked
    vault.unlock("haslo123")
    assert vault.get_profile(pid)["name"] == "X"


def test_wrong_password(vault):
    from vault import VaultError
    vault.create("haslo123")
    vault.lock()
    with pytest.raises(VaultError):
        vault.unlock("zle-haslo")


def test_corrupt_file(vault, tmp_path):
    from vault import VaultError
    vault.create("haslo123")
    vault.lock()
    (tmp_path / "vault.enc").write_text("{ to nie jest json")
    with pytest.raises(VaultError):
        vault.unlock("haslo123")


def test_profiles_crud(vault):
    vault.create("haslo123")
    p = vault.add_profile({"name": "A", "host": "h", "forwards": []})
    pid = p["id"]
    assert len(vault.profiles) == 1
    vault.update_profile(pid, {"name": "B", "host": "h2", "forwards": []})
    assert vault.get_profile(pid)["name"] == "B"
    vault.delete_profile(pid)
    assert vault.profiles == []


def test_persisted_across_instances(vault, tmp_path, monkeypatch):
    import vault as vaultmod
    vault.create("haslo123")
    vault.add_profile({"name": "Trwały", "host": "h", "forwards": []})
    # nowa instancja, ten sam plik
    v2 = vaultmod.Vault()
    v2.unlock("haslo123")
    assert v2.profiles[0]["name"] == "Trwały"


def test_change_password(vault):
    from vault import VaultError
    vault.create("stare123")
    vault.add_profile({"name": "X", "host": "h", "forwards": []})
    vault.change_password("stare123", "nowe456")
    vault.lock()
    with pytest.raises(VaultError):
        vault.unlock("stare123")           # stare hasło już nie działa
    vault.unlock("nowe456")
    assert vault.profiles[0]["name"] == "X"  # dane zachowane


def test_change_password_wrong_current(vault):
    from vault import VaultError
    vault.create("stare123")
    with pytest.raises(VaultError):
        vault.change_password("bledne", "nowe456")


def test_locked_access_raises(vault):
    from vault import VaultError
    vault.create("haslo123")
    vault.lock()
    with pytest.raises(VaultError):
        _ = vault.profiles
