"""Tunnelbox — panel WWW do zarządzania połączeniami VPN (Forti SSL-VPN / IPsec)."""

import base64
import binascii
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

import i18n
import ipsec
import updates
from connections import (
    LOCAL_PORT_MAX,
    LOCAL_PORT_MIN,
    ConnectionError_,
    ConnectionManager,
    token_mode,
)
from vault import Vault, VaultError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    manager.disconnect_all()


def _read_version() -> str:
    """Numer wersji panelu. W obrazie plik leży obok kodu (Dockerfile kopiuje
    VERSION do /app), a przy uruchomieniu ze źródeł — w katalogu wyżej."""
    here = Path(__file__).resolve().parent
    for path in (here / "VERSION", here.parent / "VERSION"):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "dev"


VERSION = _read_version()

# Sposób instalacji — od niego zależy, co panel podpowiada przy aktualizacji.
# "registry" = obraz z rejestru (docker-compose.yml w katalogu głównym): aktualizuje
# się go `docker compose pull`, instalator paczki nie ma tu czego podmieniać.
# "source" = uruchomienie ze źródeł (docker-compose.build.yml). Paczka ZIP zmiennej
# nie ustawia — API podaje wtedy "package".
INSTALL = os.environ.get("TUNNELBOX_INSTALL", "")

app = FastAPI(title="Tunnelbox", lifespan=lifespan)

# Panel odpowiada wyłącznie pod nazwami tego komputera: 127.0.0.1 (skrypty, instalator),
# localhost i *.localhost (np. tunnelbox.localhost).
# Słuchanie na pętli zwrotnej nie wystarcza: strona z internetu może przepiąć swoją
# domenę na 127.0.0.1 (DNS rebinding) i wołać API jako „ta sama strona" — np. pobrać
# zaszyfrowany sejf (eksport działa bez sesji) albo podmienić konfigurację importem.
# Przeglądarka wysyła wtedy nagłówek Host z obcą domeną, więc taka prośba dostaje 400.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "*.localhost"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

vault = Vault()
manager = ConnectionManager()
_session = {"token": None}


# --- modele ---

def _no_control(value: str) -> str:
    if any(ord(c) < 32 for c in value):
        raise ValueError(i18n.t("val.control"))
    return value


class PasswordBody(BaseModel):
    password: str = Field(min_length=4)


class ChangePasswordBody(BaseModel):
    current: str = Field(min_length=1)
    new: str = Field(min_length=4)


class ImportBody(BaseModel):
    data: str = Field(min_length=1)      # zawartość pliku, base64
    password: str = Field(min_length=1)  # hasło do importowanego pliku


# Ustawienia panelu (zapisywane w sejfie). fast_rdp = kliknięcie „Połącz przez RDP"
# uruchamia pulpit zdalny przez lokalny helper; wyłączone = przycisk pobiera plik .rdp.
# check_updates = panel pyta GitHuba o nowsze wydanie (raz na dobę, patrz updates.py);
# wyłączone = panel nie wychodzi do sieci po nic poza samym VPN-em.
# lang = język panelu ("en" albo "pl"); backend mówi tym samym, bo jego komunikaty
# lądują w interfejsie (patrz i18n.py).
DEFAULT_SETTINGS = {"fast_rdp": True, "check_updates": True, "lang": i18n.DEFAULT_LANG}


class SettingsModel(BaseModel):
    fast_rdp: bool = True
    check_updates: bool = True
    lang: str = i18n.DEFAULT_LANG

    @field_validator("lang")
    @classmethod
    def _lang_ok(cls, v):
        if v not in i18n.MESSAGES:
            raise ValueError(i18n.t("val.lang"))
        return v


class ForwardModel(BaseModel):
    label: str = ""
    ip: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    remote_port: int = Field(ge=1, le=65535)
    local_port: int | None = Field(default=None, ge=LOCAL_PORT_MIN, le=LOCAL_PORT_MAX)

    @field_validator("label")
    @classmethod
    def _label_ok(cls, v):
        return _no_control(v)


class ProfileModel(BaseModel):
    name: str = Field(min_length=1)
    # typ tunelu: "ssl" (Forti SSL-VPN) | "ipsec". Brak pola = profil sprzed IPsec.
    vpn_type: str = "ssl"
    host: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    port: int = Field(default=443, ge=1, le=65535)
    # login i hasło są wymagane zawsze poza IPsec-em uwierzytelnianym samym kluczem
    # PSK — pilnuje tego walidator całego modelu (_spojnosc_profilu)
    username: str = ""
    password: str = ""
    # realm/ścieżka z adresu bramy FortiGate (część po ukośniku, np. "myrealm")
    realm: str = ""
    # tryb tokena: "none" | "code" (kod jednorazowy) | "push" (zatwierdzenie w aplikacji)
    token_mode: str = "none"
    requires_token: bool = False  # zgodność wstecz — wyliczane z token_mode
    trusted_certs: list[str] = []
    forwards: list[ForwardModel] = []

    # --- pola wyłącznie dla IPsec ---
    # tryb uwierzytelniania; wartość niesie też wersję IKE (patrz ipsec.AUTH_MODES)
    ipsec_auth: str = ipsec.DEFAULT_AUTH
    ipsec_psk: str = ""            # klucz współdzielony bramy
    ipsec_local_id: str = ""       # identyfikator lokalny / nazwa grupy (opcjonalnie)
    ipsec_remote_id: str = ""      # identyfikator bramy (opcjonalnie)
    ipsec_remote_ts: str = ""      # sieci za VPN-em, CIDR po przecinku; puste = 0.0.0.0/0
    ipsec_aggressive: bool = False  # tryb agresywny (tylko IKEv1)

    @field_validator("realm")
    @classmethod
    def _realm_ok(cls, v):
        v = v.strip().strip("/")
        if v and not re.match(r"^[A-Za-z0-9_./-]+$", v):
            raise ValueError(i18n.t("val.realmChars"))
        return v

    @field_validator("token_mode")
    @classmethod
    def _token_mode_ok(cls, v):
        if v not in ("none", "code", "push"):
            raise ValueError(i18n.t("val.tokenMode"))
        return v

    @field_validator("vpn_type")
    @classmethod
    def _vpn_type_ok(cls, v):
        if v not in ("ssl", "ipsec"):
            raise ValueError(i18n.t("val.vpnType"))
        return v

    @field_validator("ipsec_auth")
    @classmethod
    def _ipsec_auth_ok(cls, v):
        if v not in ipsec.AUTH_MODES:
            raise ValueError(i18n.t("val.ipsecAuth"))
        return v

    @field_validator("ipsec_local_id", "ipsec_remote_id")
    @classmethod
    def _ipsec_id_ok(cls, v):
        v = v.strip()
        if v and not re.match(r"^[A-Za-z0-9_.@:-]+$", v):
            raise ValueError(i18n.t("val.ipsecIdChars"))
        return v

    @field_validator("ipsec_remote_ts")
    @classmethod
    def _ipsec_remote_ts_ok(cls, v):
        nets = [n.strip() for n in v.replace(";", ",").split(",") if n.strip()]
        for net in nets:
            if not re.match(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$", net):
                raise ValueError(i18n.t("val.network", net=net))
        return ",".join(nets)

    @field_validator("ipsec_psk")
    @classmethod
    def _ipsec_psk_ok(cls, v):
        return _no_control(v)

    @model_validator(mode="after")
    def _spojnosc_profilu(self):
        # requires_token trzymamy spójne z token_mode (stare miejsca korzystają z niego)
        self.requires_token = self.token_mode != "none"
        if self.vpn_type == "ipsec":
            if not self.ipsec_psk:
                raise ValueError(i18n.t("val.pskRequired"))
            if self.token_mode == "push":
                raise ValueError(i18n.t("val.ipsecNoPush"))
            if not ipsec.uses_user_auth(self.ipsec_auth):
                # tryby na sam klucz PSK nie pytają o użytkownika — login i hasło
                # są wtedy zbędne, ale token bez pola hasła nie ma dokąd trafić
                if self.token_mode != "none":
                    raise ValueError(i18n.t("val.ipsecNoUser"))
                return self
        if not self.username:
            raise ValueError(i18n.t("val.usernameRequired"))
        if not self.password:
            raise ValueError(i18n.t("val.passwordRequired"))
        return self

    @field_validator("name", "username")
    @classmethod
    def _text_ok(cls, v):
        return _no_control(v)

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v):
        _no_control(v)
        if v != v.strip():
            raise ValueError(i18n.t("val.passwordSpaces"))
        return v

    @field_validator("trusted_certs")
    @classmethod
    def _certs_ok(cls, v):
        for cert in v:
            if not (len(cert) >= 32 and all(c in "0123456789abcdefABCDEF" for c in cert)):
                raise ValueError(i18n.t("val.fingerprint"))
        return v


class ConnectBody(BaseModel):
    otp: str | None = None


# --- autoryzacja ---

def _require_auth(x_auth: str | None):
    if (
        not vault.unlocked
        or not _session["token"]
        or not x_auth
        or not secrets.compare_digest(x_auth.encode(), _session["token"].encode())
    ):
        raise HTTPException(status_code=401, detail=i18n.t("api.locked"))


def _open_session() -> str:
    _session["token"] = secrets.token_hex(16)
    _apply_lang()
    return _session["token"]


def _apply_lang() -> str:
    """Ustawia język komunikatów backendu na ten wybrany w panelu. Wołane po każdym
    otwarciu sejfu (wtedy dopiero widać ustawienia) i po zapisie ustawień."""
    with vault.transaction():
        chosen = {**DEFAULT_SETTINGS, **vault.settings}["lang"]
    return i18n.set_lang(str(chosen))


# --- sejf ---

@app.get("/api/vault")
def vault_status():
    # wersja jedzie tym (publicznym) endpointem, żeby było ją widać także na
    # ekranie logowania — panel i tak słucha wyłącznie na pętli zwrotnej
    return {"exists": vault.exists, "unlocked": vault.unlocked, "version": VERSION}


@app.post("/api/vault/create")
def vault_create(body: PasswordBody):
    try:
        vault.create(body.password)
    except VaultError as e:
        raise HTTPException(400, str(e))
    return {"token": _open_session()}


@app.post("/api/vault/unlock")
def vault_unlock(body: PasswordBody):
    try:
        vault.unlock(body.password)
    except VaultError as e:
        raise HTTPException(400, str(e))
    return {"token": _open_session()}


@app.post("/api/vault/change-password")
def vault_change_password(body: ChangePasswordBody, x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    try:
        vault.change_password(body.current, body.new)
    except VaultError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/vault/lock")
def vault_lock(x_auth: str | None = Header(default=None)):
    """Blokuje panel. Aktywne połączenia VPN celowo działają dalej —
    blokada dotyczy dostępu do konfiguracji, nie tuneli."""
    _require_auth(x_auth)
    vault.lock()
    _session["token"] = None
    return {"ok": True}


@app.get("/api/vault/export")
def vault_export():
    """Pobranie zaszyfrowanego pliku konfiguracji (kopia zapasowa/przeniesienie).

    Plik jest zaszyfrowany hasłem głównym, a panel słucha wyłącznie lokalnie —
    pobranie go jest równoważne skopiowaniu pliku z dysku, więc działa też
    na ekranie logowania.
    """
    try:
        data = vault.export_bytes()
    except VaultError as e:
        raise HTTPException(404, str(e))
    stamp = datetime.now().strftime("%Y-%m-%d")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition":
                 f'attachment; filename="tunnelbox-config-{stamp}.enc"'},
    )


@app.post("/api/vault/import")
def vault_import(body: ImportBody):
    """Wczytuje plik konfiguracji. Wymaga hasła do TEGO pliku, więc nie da się
    podmienić konfiguracji przypadkowym plikiem. Poprzednia wersja jest kopiowana
    obok jako `vault-<data>.enc.bak`."""
    try:
        raw = base64.b64decode(body.data, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, i18n.t("api.badFile"))
    # konfiguracja jest zastępowana w całości — tunele odnosiłyby się do profili,
    # których już nie ma
    manager.disconnect_all()
    try:
        vault.import_bytes(raw, body.password)
    except VaultError as e:
        raise HTTPException(400, str(e))
    return {"token": _open_session()}


# --- stan ---

@app.get("/api/state")
def get_state(x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    with vault.transaction():
        profiles = [dict(p) for p in vault.profiles]
        settings = {**DEFAULT_SETTINGS, **vault.settings}
    return {
        "profiles": profiles,
        "connections": manager.status(),
        "port_range": [LOCAL_PORT_MIN, LOCAL_PORT_MAX],
        "settings": settings,
        # także tutaj, bo stan jest zawsze wczytany, zanim pojawi się przycisk RDP —
        # /api/update potrafi się spóźnić, gdy GitHub odpowiada wolno
        "install": INSTALL or "package",
    }


@app.put("/api/settings")
def update_settings(body: SettingsModel, x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    saved = vault.update_settings(body.model_dump())
    _apply_lang()
    return {**DEFAULT_SETTINGS, **saved}


# --- aktualizacje ---

def _updates_enabled() -> bool:
    with vault.transaction():
        return bool({**DEFAULT_SETTINGS, **vault.settings}["check_updates"])


def _update_info(force: bool = False) -> dict:
    # sposób instalacji jedzie zawsze, także przy wyłączonym sprawdzaniu
    install = INSTALL or "package"
    if not _updates_enabled():
        return {**updates.empty(VERSION), "enabled": False, "install": install}
    return {**updates.check(VERSION, force=force), "enabled": True, "install": install}


@app.get("/api/update")
def update_status(x_auth: str | None = Header(default=None)):
    """Czy jest nowsza wersja. Wynik jest zapamiętywany na dobę, więc panel
    może pytać o niego przy każdym otwarciu — do GitHuba i tak nic nie leci."""
    _require_auth(x_auth)
    return _update_info()


@app.post("/api/update/check")
def update_check(x_auth: str | None = Header(default=None)):
    """„Sprawdź teraz" — pomija pamięć podręczną."""
    _require_auth(x_auth)
    return _update_info(force=True)


# --- profile ---

@app.post("/api/profiles")
def create_profile(body: ProfileModel, x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    with vault.transaction():
        profile = body.model_dump()
        _assign_local_ports(profile, exclude_id=None)
        return vault.add_profile(profile)


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfileModel,
                   x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    if manager.is_active(profile_id):
        raise HTTPException(409, i18n.t("api.disconnectFirst"))
    with vault.transaction():
        _get_profile_or_404(profile_id)
        profile = body.model_dump()
        _assign_local_ports(profile, exclude_id=profile_id)
        result = vault.update_profile(profile_id, profile)
    manager.reset(profile_id)  # skasuj wiszący stan (np. need_trust ze starego hosta)
    return result


@app.post("/api/profiles/{profile_id}/forwards")
def add_forward(profile_id: str, body: ForwardModel,
                x_auth: str | None = Header(default=None)):
    """Dokłada maszynę do profilu; jeśli połączenie działa — uruchamia ją od razu."""
    _require_auth(x_auth)
    fwd = body.model_dump()
    with vault.transaction():
        profile = _get_profile_or_404(profile_id)
        used = {f["local_port"]
                for other in vault.profiles
                for f in other.get("forwards", [])
                if f.get("local_port")}
        if fwd.get("local_port"):
            if fwd["local_port"] in used:
                raise HTTPException(400, i18n.t("api.portTaken", port=fwd["local_port"]))
        else:
            free = next((p for p in range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1) if p not in used),
                        None)
            if free is None:
                raise HTTPException(400, i18n.t("api.noFreePorts"))
            fwd["local_port"] = free
        profile.setdefault("forwards", []).append(fwd)
        vault.save()

    if manager.is_active(profile_id):
        try:
            manager.add_forward_live(profile_id, fwd)
        except ConnectionError_ as e:
            # nie udało się uruchomić na żywo — wycofaj wpis, żeby stan był spójny
            with vault.transaction():
                profile = vault.get_profile(profile_id)
                profile["forwards"] = [f for f in profile["forwards"]
                                       if f["local_port"] != fwd["local_port"]]
                vault.save()
            raise HTTPException(409, i18n.t("api.addMachineFailed", error=e))
    return fwd


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str, x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    if manager.is_active(profile_id):
        raise HTTPException(409, i18n.t("api.disconnectFirst"))
    with vault.transaction():
        _get_profile_or_404(profile_id)
        vault.delete_profile(profile_id)
    manager.reset(profile_id)
    return {"ok": True}


# --- połączenia ---

@app.post("/api/profiles/{profile_id}/connect")
def connect(profile_id: str, body: ConnectBody,
            x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    profile = _get_profile_or_404(profile_id)
    if token_mode(profile) == "code" and not (body.otp and body.otp.strip()):
        raise HTTPException(400, i18n.t("api.tokenRequired"))
    try:
        manager.connect(profile, body.otp.strip() if body.otp else None)
    except ConnectionError_ as e:
        # kod pozwala panelowi odróżnić nieszkodliwy dwuklik od prawdziwej awarii
        raise HTTPException(409, {"code": e.code, "message": str(e)} if e.code else str(e))
    return {"ok": True}


@app.post("/api/profiles/{profile_id}/disconnect")
def disconnect(profile_id: str, x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    manager.disconnect(profile_id)
    return {"ok": True}


@app.post("/api/profiles/{profile_id}/trust")
def trust_certificate(profile_id: str, x_auth: str | None = Header(default=None)):
    _require_auth(x_auth)
    with vault.transaction():
        profile = _get_profile_or_404(profile_id)
        cert = manager.take_pending_cert(profile_id)
        if not cert:
            raise HTTPException(409, i18n.t("api.noPendingCert"))
        if cert not in profile.setdefault("trusted_certs", []):
            profile["trusted_certs"].append(cert)
        vault.save()
    return {"ok": True}


# --- pomocnicze ---

def _get_profile_or_404(profile_id: str) -> dict:
    try:
        return vault.get_profile(profile_id)
    except VaultError:
        raise HTTPException(404, i18n.t("api.profileMissing"))


def _assign_local_ports(profile: dict, exclude_id: str | None):
    """Nadaje wolne porty lokalne i pilnuje unikalności w całym sejfie."""
    used = set()
    for other in vault.profiles:
        if other["id"] == exclude_id:
            continue
        for fwd in other.get("forwards", []):
            used.add(fwd["local_port"])

    for fwd in profile["forwards"]:
        port = fwd.get("local_port")
        if port:
            if port in used:
                raise HTTPException(400, i18n.t("api.portTaken", port=port))
            used.add(port)

    for fwd in profile["forwards"]:
        if not fwd.get("local_port"):
            free = next(
                (p for p in range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1) if p not in used),
                None,
            )
            if free is None:
                raise HTTPException(400, i18n.t("api.noFreePorts"))
            fwd["local_port"] = free
            used.add(free)


_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
