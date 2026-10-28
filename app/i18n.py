"""Komunikaty backendu po angielsku (domyślnie) i po polsku.

Panel pokazuje te teksty tak samo jak swoje własne — w błędach walidacji, na kartach
połączeń i w logu połączenia — więc muszą mówić tym samym językiem, co reszta
interfejsu. Język bierze się z ustawień panelu (`lang` w sejfie): main.py ustawia go
po odblokowaniu sejfu i przy każdym zapisie ustawień.

Jeden język na cały proces, a nie na żądanie: część komunikatów powstaje w wątkach
pilnujących tuneli, długo po tym, jak żądanie się skończyło.
"""

DEFAULT_LANG = "en"

MESSAGES = {
    "en": {
        # walidacja formularza (pydantic -> 422 -> „Check the field…")
        "val.control": "the field cannot contain control characters or line breaks",
        "val.tokenMode": "invalid token mode",
        "val.vpnType": "invalid connection type",
        "val.ipsecAuth": "invalid IPsec authentication mode",
        "val.network": "{net} does not look like a network address (e.g. 10.0.0.0/8)",
        "val.pskRequired": "an IPsec connection needs a pre-shared key (PSK)",
        "val.ipsecNoPush": (
            "IPsec cannot approve sign-ins on a phone (push) — pick the one-time code "
            "or turn the token off"
        ),
        "val.ipsecNoUser": (
            "the chosen IPsec mode does not authenticate a user, so it cannot use a token"
        ),
        "val.passwordRequired": "a password is required",
        "val.passwordSpaces": (
            "the VPN client cannot handle a password starting or ending with a space — "
            "remove it or change the password on the VPN side"
        ),
        "val.fingerprint": "invalid certificate fingerprint",
        "val.lang": "unsupported language",
        # API
        "api.badFile": "Invalid file.",
        "api.disconnectFirst": "Disconnect this connection first.",
        "api.portTaken": "Local port {port} is already taken.",
        "api.noFreePorts": "No free local ports left.",
        "api.addMachineFailed": "Could not add the machine: {error}",
        "api.tokenRequired": "This connection needs a code (token).",
        "api.noPendingCert": "No certificate is waiting to be accepted.",
        "api.locked": "The vault is locked.",
        # sejf
        "vault.exists": "The vault already exists.",
        "vault.badPassword": "Wrong master password.",
        "vault.badImportPassword": "Wrong password for the imported file.",
        "vault.badCurrentPassword": "Wrong current master password.",
        # połączenia
        "conn.alreadyActive": "This connection is already active.",
        "conn.tooMany": "Too many connections at once.",
        "conn.unknownCert": "The VPN server presented an unknown certificate.",
        "conn.dropped": "The VPN connection was dropped.",
        "conn.failed": "Could not establish the connection — see the log for details.",
        "conn.internal": "Internal error: {error}",
        "conn.authRejected": "Sign-in rejected — check the username, password or token.",
        "conn.unreachable": (
            "Cannot reach the VPN server — check the server address and your internet connection."
        ),
        "conn.noPpp": (
            "This Docker environment does not provide PPP — update Docker Desktop or check "
            "the container's privileges."
        ),
        "conn.forwardsFailed": "The tunnel came up, but port forwarding failed: {error}",
        "conn.noXfrm": (
            "The kernel does not provide IPsec (XFRM) — update Docker Desktop or use an "
            "SSL-VPN connection."
        ),
        "conn.ipsecFailed": "The IPsec tunnel did not come up: {error}",
        "conn.daemonFailed": "The IPsec daemon did not start — see the log for details.",
        "conn.configFailed": "Could not load the IPsec configuration.",
        "conn.configLoaded": "IPsec configuration loaded — establishing the tunnel...",
        "conn.aborted": "Connection aborted.",
        "conn.ipsecDropped": "The IPsec tunnel was dropped.",
        "conn.notActive": "The connection is not active.",
        "conn.portInUse": "Local port {port} is already used by this connection.",
        "conn.forwardFailed": (
            "forwarding on port {port} did not start (exit code {code}) — check the remote "
            "IP and port"
        ),
        "conn.missingTool": "missing tool: {tool}",
        # IPsec — tłumaczenie logu charona na poradę
        "ipsec.authRejected": "Sign-in rejected — check the username, password or token code.",
        "ipsec.badPsk": (
            "The server rejected the PSK or the identifier — check the pre-shared key and the "
            "local identifier field."
        ),
        "ipsec.noProposal": (
            "The server accepted none of the cipher sets — ask the administrator for the phase 1 "
            "and phase 2 algorithms."
        ),
        "ipsec.badTs": "The server rejected the network range — fix the networks behind the VPN.",
        "ipsec.badParams": (
            "The server rejected the connection parameters — check the local identifier and "
            "aggressive mode."
        ),
        "ipsec.unreachable": (
            "Cannot reach the VPN server — check the gateway address and your internet connection "
            "(IPsec needs UDP ports 500 and 4500)."
        ),
        "ipsec.kernelRejected": "The kernel rejected the IPsec configuration — update Docker Desktop.",
        "ipsec.gatewaySilent": (
            "The gateway is not answering — check the server address and whether your network "
            "passes IPsec through (UDP 500 and 4500)."
        ),
        "ipsec.timeout": "Could not establish the IPsec tunnel — see the log for details.",
        "val.realmChars": "the realm contains characters that are not allowed",
        "val.ipsecIdChars": "the IPsec identifier contains characters that are not allowed",
        "val.usernameRequired": "a username is required",
        "api.profileMissing": "No such profile.",
        "vault.missing": "The vault does not exist.",
        "vault.corrupt": "The vault file is damaged.",
        "vault.profileMissing": "No such profile.",
        "vault.nothingToExport": "There is no configuration to export.",
        "vault.notOurFile": "This is not a Tunnelbox configuration file.",
        "vault.importCorrupt": "The imported file is damaged.",
        "vault.locked": "The vault is locked.",
        "conn.saMissing": "IPsec tunnel with no active SA ({misses}/{total}) — waiting for it to come back...",
        "conn.diagStart": "--- tunnel diagnostics ---",
        "conn.diagEnd": "--- end of diagnostics ---",
        "conn.route": "route: {line}",
        "conn.routeTo": "route to {ip}: {line}",
    },
    "pl": {
        "val.control": "pole nie może zawierać znaków sterujących ani nowej linii",
        "val.tokenMode": "nieprawidłowy tryb tokena",
        "val.vpnType": "nieprawidłowy typ połączenia",
        "val.ipsecAuth": "nieprawidłowy tryb uwierzytelniania IPsec",
        "val.network": "{net} nie wygląda na adres sieci (np. 10.0.0.0/8)",
        "val.pskRequired": "połączenie IPsec wymaga klucza współdzielonego (PSK)",
        "val.ipsecNoPush": (
            "IPsec nie obsługuje zatwierdzania na telefonie (push) — wybierz "
            "kod jednorazowy albo wyłącz token"
        ),
        "val.ipsecNoUser": (
            "wybrany tryb IPsec nie uwierzytelnia użytkownika, więc nie może korzystać z tokena"
        ),
        "val.passwordRequired": "hasło jest wymagane",
        "val.passwordSpaces": (
            "klient VPN nie obsługuje hasła zaczynającego się lub kończącego "
            "spacją — usuń ją albo zmień hasło po stronie VPN"
        ),
        "val.fingerprint": "nieprawidłowy odcisk certyfikatu",
        "val.lang": "nieobsługiwany język",
        "api.badFile": "Nieprawidłowy plik.",
        "api.disconnectFirst": "Najpierw rozłącz to połączenie.",
        "api.portTaken": "Port lokalny {port} jest już zajęty.",
        "api.noFreePorts": "Brak wolnych portów lokalnych.",
        "api.addMachineFailed": "Nie udało się dodać maszyny: {error}",
        "api.tokenRequired": "To połączenie wymaga kodu (tokena).",
        "api.noPendingCert": "Brak certyfikatu oczekującego na akceptację.",
        "api.locked": "Sejf jest zablokowany.",
        "vault.exists": "Sejf już istnieje.",
        "vault.badPassword": "Nieprawidłowe hasło główne.",
        "vault.badImportPassword": "Nieprawidłowe hasło do importowanego pliku.",
        "vault.badCurrentPassword": "Nieprawidłowe obecne hasło główne.",
        "conn.alreadyActive": "To połączenie jest już aktywne.",
        "conn.tooMany": "Zbyt wiele równoległych połączeń.",
        "conn.unknownCert": "Serwer VPN przedstawił nieznany certyfikat.",
        "conn.dropped": "Połączenie VPN zostało zerwane.",
        "conn.failed": "Nie udało się nawiązać połączenia — szczegóły w logu.",
        "conn.internal": "Błąd wewnętrzny: {error}",
        "conn.authRejected": "Logowanie odrzucone — sprawdź login, hasło lub token.",
        "conn.unreachable": (
            "Nie można połączyć się z serwerem VPN — sprawdź adres serwera i połączenie "
            "z internetem."
        ),
        "conn.noPpp": (
            "Środowisko Docker nie udostępnia PPP — zaktualizuj Docker Desktop lub sprawdź "
            "uprawnienia kontenera."
        ),
        "conn.forwardsFailed": "Tunel wstał, ale przekierowania portów zawiodły: {error}",
        "conn.noXfrm": (
            "Jądro nie udostępnia IPsec (XFRM) — zaktualizuj Docker Desktop albo użyj "
            "połączenia SSL-VPN."
        ),
        "conn.ipsecFailed": "Tunel IPsec nie wstał: {error}",
        "conn.daemonFailed": "Demon IPsec nie wystartował — szczegóły w logu.",
        "conn.configFailed": "Nie udało się wczytać konfiguracji IPsec.",
        "conn.configLoaded": "Konfiguracja IPsec wczytana — nawiązuję tunel...",
        "conn.aborted": "Połączenie przerwane.",
        "conn.ipsecDropped": "Tunel IPsec został zerwany.",
        "conn.notActive": "Połączenie nie jest aktywne.",
        "conn.portInUse": "Port lokalny {port} jest już używany w tym połączeniu.",
        "conn.forwardFailed": (
            "przekierowanie na port {port} nie wystartowało (kod {code}) — sprawdź IP "
            "i port zdalny"
        ),
        "conn.missingTool": "brak narzędzia: {tool}",
        "ipsec.authRejected": "Logowanie odrzucone — sprawdź login, hasło lub kod tokena.",
        "ipsec.badPsk": (
            "Serwer odrzucił klucz PSK lub identyfikator — sprawdź klucz współdzielony "
            "i pole identyfikatora lokalnego."
        ),
        "ipsec.noProposal": (
            "Serwer nie zaakceptował żadnego zestawu szyfrów — poproś administratora "
            "o algorytmy fazy 1 i 2."
        ),
        "ipsec.badTs": "Serwer odrzucił zakres sieci — popraw pole z sieciami za VPN-em.",
        "ipsec.badParams": (
            "Serwer odrzucił parametry połączenia — sprawdź identyfikator lokalny "
            "i tryb agresywny."
        ),
        "ipsec.unreachable": (
            "Nie można połączyć się z serwerem VPN — sprawdź adres bramy i połączenie "
            "z internetem (IPsec potrzebuje portów UDP 500 i 4500)."
        ),
        "ipsec.kernelRejected": "Jądro odrzuciło konfigurację IPsec — zaktualizuj Docker Desktop.",
        "ipsec.gatewaySilent": (
            "Brama nie odpowiada — sprawdź adres serwera i to, czy sieć przepuszcza "
            "IPsec (UDP 500 i 4500)."
        ),
        "ipsec.timeout": "Nie udało się zestawić tunelu IPsec — szczegóły w logu.",
        "val.realmChars": "realm zawiera niedozwolone znaki",
        "val.ipsecIdChars": "identyfikator IPsec zawiera niedozwolone znaki",
        "val.usernameRequired": "login jest wymagany",
        "api.profileMissing": "Profil nie istnieje.",
        "vault.missing": "Sejf nie istnieje.",
        "vault.corrupt": "Plik sejfu jest uszkodzony.",
        "vault.profileMissing": "Profil nie istnieje.",
        "vault.nothingToExport": "Brak konfiguracji do wyeksportowania.",
        "vault.notOurFile": "To nie jest plik konfiguracji Tunnelbox.",
        "vault.importCorrupt": "Importowany plik jest uszkodzony.",
        "vault.locked": "Sejf jest zablokowany.",
        "conn.saMissing": "Tunel IPsec bez aktywnego SA ({misses}/{total}) — czekam na odtworzenie...",
        "conn.diagStart": "--- diagnostyka tunelu ---",
        "conn.diagEnd": "--- koniec diagnostyki ---",
        "conn.route": "trasa: {line}",
        "conn.routeTo": "trasa do {ip}: {line}",
    },
}

_lang = DEFAULT_LANG


def set_lang(code: str) -> str:
    """Ustawia język komunikatów. Nieznany kod zostawia poprzedni."""
    global _lang
    if code in MESSAGES:
        _lang = code
    return _lang


def current_lang() -> str:
    return _lang


def t(key: str, **params) -> str:
    """Komunikat w bieżącym języku. Brak klucza nie może wywrócić panelu —
    wracamy do angielskiego, a w ostateczności zwracamy sam klucz."""
    text = MESSAGES[_lang].get(key) or MESSAGES[DEFAULT_LANG].get(key)
    if text is None:
        return key
    return text.format(**params) if params else text
