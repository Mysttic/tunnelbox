"""Sejf z profilami VPN — plik zaszyfrowany hasłem głównym (scrypt + AES-256-GCM)."""

import base64
import json
import os
import secrets
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from i18n import t

VAULT_PATH = Path(os.environ.get("VAULT_PATH", "/data/vault.enc"))


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class VaultError(Exception):
    pass


class Vault:
    def __init__(self):
        self._key = None
        self._salt = None
        self._data = None  # {"profiles": [...]}
        self._lock = threading.RLock()

    @property
    def exists(self) -> bool:
        return VAULT_PATH.exists()

    @property
    def unlocked(self) -> bool:
        return self._key is not None

    def transaction(self):
        """Context manager do atomowej sekwencji odczyt-zmień-zapis w endpointach."""
        return self._lock

    def create(self, password: str):
        with self._lock:
            if self.exists:
                raise VaultError(t("vault.exists"))
            self._salt = secrets.token_bytes(16)
            self._key = self._derive(password, self._salt)
            self._data = {"profiles": [], "settings": {}}
            self._write()

    def unlock(self, password: str):
        with self._lock:
            if not self.exists:
                raise VaultError(t("vault.missing"))
            try:
                raw = json.loads(VAULT_PATH.read_text())
                salt = base64.b64decode(raw["salt"])
                nonce = base64.b64decode(raw["nonce"])
                blob = base64.b64decode(raw["data"])
            except (ValueError, KeyError, TypeError, OSError):
                raise VaultError(t("vault.corrupt"))
            key = self._derive(password, salt)
            try:
                plain = AESGCM(key).decrypt(nonce, blob, None)
            except InvalidTag:
                raise VaultError(t("vault.badPassword"))
            try:
                self._data = json.loads(plain)
            except ValueError:
                raise VaultError(t("vault.corrupt"))
            # sejfy z wcześniejszych wersji nie mają sekcji ustawień
            self._data.setdefault("settings", {})
            self._key = key
            self._salt = salt

    def lock(self):
        with self._lock:
            self._key = None
            self._salt = None
            self._data = None

    # --- profile ---

    @property
    def profiles(self) -> list:
        self._require_unlocked()
        return self._data["profiles"]

    # --- ustawienia panelu ---

    @property
    def settings(self) -> dict:
        self._require_unlocked()
        return self._data.setdefault("settings", {})

    def update_settings(self, patch: dict) -> dict:
        with self._lock:
            self._require_unlocked()
            self._data.setdefault("settings", {}).update(patch)
            self._write()
            return self._data["settings"]

    def get_profile(self, profile_id: str) -> dict:
        with self._lock:
            for p in self.profiles:
                if p["id"] == profile_id:
                    return p
        raise VaultError(t("vault.profileMissing"))

    def add_profile(self, profile: dict) -> dict:
        with self._lock:
            self._require_unlocked()
            profile["id"] = secrets.token_hex(4)
            self._data["profiles"].append(profile)
            self._write()
            return profile

    def update_profile(self, profile_id: str, profile: dict) -> dict:
        with self._lock:
            existing = self.get_profile(profile_id)
            profile["id"] = profile_id
            idx = self._data["profiles"].index(existing)
            self._data["profiles"][idx] = profile
            self._write()
            return profile

    def delete_profile(self, profile_id: str):
        with self._lock:
            existing = self.get_profile(profile_id)
            self._data["profiles"].remove(existing)
            self._write()

    def save(self):
        with self._lock:
            self._require_unlocked()
            self._write()

    # --- eksport / import pliku konfiguracji ---

    def export_bytes(self) -> bytes:
        """Zwraca zaszyfrowany plik konfiguracji (taki, jaki leży na dysku)."""
        if not self.exists:
            raise VaultError(t("vault.nothingToExport"))
        return VAULT_PATH.read_bytes()

    def import_bytes(self, data: bytes, password: str):
        """Wczytuje plik konfiguracji po sprawdzeniu, że hasło do niego pasuje.

        Obecna konfiguracja jest najpierw kopiowana obok (``vault-<data>.enc.bak``),
        żeby import nigdy nie skasował danych bezpowrotnie.
        """
        with self._lock:
            try:
                raw = json.loads(data.decode("utf-8"))
                salt = base64.b64decode(raw["salt"])
                nonce = base64.b64decode(raw["nonce"])
                blob = base64.b64decode(raw["data"])
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                raise VaultError(t("vault.notOurFile"))

            key = self._derive(password, salt)
            try:
                plain = AESGCM(key).decrypt(nonce, blob, None)
            except InvalidTag:
                raise VaultError(t("vault.badImportPassword"))
            try:
                parsed = json.loads(plain)
            except ValueError:
                raise VaultError(t("vault.importCorrupt"))

            VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
            if VAULT_PATH.exists():
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(VAULT_PATH, VAULT_PATH.with_name(f"vault-{stamp}.enc.bak"))

            VAULT_PATH.write_bytes(data)
            self._key = key
            self._salt = salt
            self._data = parsed
            self._data.setdefault("profiles", [])
            self._data.setdefault("settings", {})

    def change_password(self, current: str, new: str):
        """Zmienia hasło główne — weryfikuje obecne i re-szyfruje sejf nowym kluczem."""
        with self._lock:
            self._require_unlocked()
            if not secrets.compare_digest(self._derive(current, self._salt), self._key):
                raise VaultError(t("vault.badCurrentPassword"))
            self._salt = secrets.token_bytes(16)
            self._key = self._derive(new, self._salt)
            self._write()

    # --- wewnętrzne ---

    def _require_unlocked(self):
        if not self.unlocked:
            raise VaultError(t("vault.locked"))

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
        return kdf.derive(password.encode())

    def _write(self):
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self._key).encrypt(
            nonce, json.dumps(self._data).encode(), None
        )
        payload = json.dumps(
            {"salt": _b64(self._salt), "nonce": _b64(nonce), "data": _b64(ciphertext)}
        )
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(VAULT_PATH.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, VAULT_PATH)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        # utrwal sam rename (best-effort — na niektórych systemach plików katalog
        # nie da się fsyncować i to normalne)
        try:
            dir_fd = os.open(str(VAULT_PATH.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
