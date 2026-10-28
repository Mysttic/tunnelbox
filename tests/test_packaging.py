"""Testy pakietu instalacyjnego, plików compose i workflow wydania.

Skrypty startowe uruchamiają się u użytkowników (Windows, Mac, Linux), a workflow publikuje
to, co czytają zainstalowane już panele i instalatory — błąd wychodzi dopiero u nich.
"""

import json
import pathlib
import re

import pytest

from connections import LOCAL_PORT_MAX, LOCAL_PORT_MIN, local_host

ROOT = pathlib.Path(__file__).parent.parent
PS1_FILES = sorted(ROOT.glob("*.ps1")) + sorted((ROOT / "packaging").glob("*.ps1"))


def tekst(sciezka: str) -> str:
    """Treść pliku z repozytorium. Pliki .ps1 mają BOM (test_ps1_ma_bom) — utf-8-sig go zdejmuje."""
    plik = ROOT / sciezka
    return plik.read_text(encoding="utf-8-sig" if plik.suffix == ".ps1" else "utf-8")


def bez_komentarzy(text: str) -> str:
    """Tekst bez linii-komentarzy (#) — żeby asercji nie spełniał sam opis w komentarzu."""
    return "".join(linia + "\n" for linia in text.splitlines() if not linia.lstrip().startswith("#"))


def joby(workflow: str) -> list[str]:
    kod = bez_komentarzy(workflow)
    return re.findall(r"^  ([\w-]+):$", kod[kod.index("\njobs:\n"):], re.M)


def job(workflow: str, nazwa: str) -> str:
    """Treść jednego joba (bez komentarzy) — od nagłówka do następnego joba."""
    kod = bez_komentarzy(workflow)
    kod = kod[kod.index("\njobs:\n"):]
    m = re.search(rf"^  {re.escape(nazwa)}:\n(.*?)(?=^  [\w-]+:$|\Z)", kod, re.M | re.S)
    assert m, f"brak joba {nazwa}"
    return m.group(1)


def kroki(job_text: str) -> list[str]:
    return re.split(r"\n(?=      - )", job_text)


def funkcja(ps1: str, nazwa: str) -> str:
    """Ciało funkcji PowerShella zdefiniowanej na najwyższym poziomie skryptu."""
    m = re.search(rf"^function {re.escape(nazwa)} \{{\n(.*?)^\}}", ps1, re.M | re.S)
    assert m, f"brak funkcji {nazwa}"
    return m.group(1)


def usluga(compose: str) -> str:
    m = re.search(r"^services:\n  ([\w-]+):$", bez_komentarzy(compose), re.M)
    assert m, "brak usługi w compose"
    return m.group(1)


def porty(compose: str) -> list[str]:
    blok = re.search(r"^    ports:\n((?:      .*\n)+)", bez_komentarzy(compose), re.M)
    assert blok, "brak sekcji ports"
    return [wpis.strip("\"'") for wpis in re.findall(r"^\s+- (\S+)", blok.group(1), re.M)]


WORKFLOW = tekst(".github/workflows/release.yml")
CI = tekst(".github/workflows/ci.yml")
LAUNCHER = tekst("packaging/update-launcher.ps1")

# Kanał aktualizacji: wydania na hubie Mysttic/Mysttic (strona z pobieraniem). Hub trzyma
# wydania kilku programów, ten ma prefiks tunnelbox-v.
HUB = "Mysttic/Mysttic"
PAGE = "https://mysttic.github.io/Mysttic/tunnelbox/"

COMPOSE = ["docker-compose.yml", "docker-compose.build.yml", "packaging/docker-compose.yml"]
COMPOSE_Z_PORTAMI = ["docker-compose.yml", "packaging/docker-compose.yml"]


@pytest.mark.parametrize("path", PS1_FILES, ids=lambda p: p.name)
def test_ps1_ma_bom(path):
    """Windows PowerShell 5.1 czyta .ps1 bez BOM jako ANSI.

    Polskie znaki rozsypują się wtedy na ekranie, a znaki takie jak „—" potrafią
    rozjechać parsowanie stringów i wywalić skrypt błędem składni.
    """
    assert path.read_bytes()[:3] == b"\xef\xbb\xbf", (
        f"{path.name} musi być zapisany jako UTF-8 z BOM"
    )


@pytest.mark.parametrize("path", PS1_FILES, ids=lambda p: p.name)
def test_ps1_dekoduje_sie_jako_utf8(path):
    path.read_text(encoding="utf-8")


def test_pakiet_zawiera_helper_rdp():
    """Helper szybkiego łączenia RDP musi trafiać do paczki release."""
    assert (ROOT / "packaging" / "rdp-launcher.ps1").is_file()
    assert "rdp-launcher.ps1" in job(WORKFLOW, "release"), "helper nie jest kopiowany do paczki"


def test_pakiet_zawiera_helper_aktualizacji():
    """Helper protokołu tunnelbox-update:// musi trafiać do paczki release —
    bez niego przycisk „Zaktualizuj" w panelu nie ma czego uruchomić."""
    assert (ROOT / "packaging" / "update-launcher.ps1").is_file()
    assert "update-launcher.ps1" in job(WORKFLOW, "release"), "helper nie jest kopiowany do paczki"


def test_start_rejestruje_protokol_aktualizacji():
    """Rejestracja dzieje się przy starcie — użytkownik nic nie klika w konsoli."""
    text = tekst("packaging/start.ps1")
    assert "Enable-Updates" in text
    assert "HKCU:\\Software\\Classes\\tunnelbox-update" in text
    assert "update-launcher.ps1" in text


def test_panel_otwiera_protokoly_ktore_rejestruje_start():
    """Przyciski panelu otwierają adresy tunnelbox-update:// i tunnelbox-rdp://. Działają
    tylko wtedy, gdy start.ps1 zarejestrował w HKCU dokładnie te protokoły — przy rozjeździe
    nazw kliknięcie w panelu nic nie robi."""
    app = tekst("app/static/app.js")
    schematy = set(re.findall(r"\b([a-z][a-z0-9]*-[a-z]+)://", app))
    assert schematy == {"tunnelbox-update", "tunnelbox-rdp"}

    start = tekst("packaging/start.ps1")
    for schemat in schematy:
        assert f'"HKCU:\\Software\\Classes\\{schemat}"' in start, f"start.ps1 nie rejestruje {schemat}://"


def test_instalator_nie_ufa_danym_ze_strony():
    """Ze strony przychodzi sam numer wersji; adres pliku helper ustala sam
    i sprawdza, czy pochodzi ze strony wydań."""
    text = LAUNCHER
    assert r"-notmatch '^\d+\.\d+\.\d+$'" in text, "brak walidacji numeru wersji"
    assert "StartsWith($DownloadPrefix" in text, "brak sprawdzenia pochodzenia pliku"


def test_instalator_przyjmuje_pliki_tylko_z_huba():
    """Pochodzenie pliku sprawdza prefiks strony wydań tego samego repozytorium, które helper
    odpytuje. GitHub nie rozróżnia wielkości liter w nazwie właściciela i repozytorium, a API
    zwraca postać kanoniczną: porównanie z rozróżnianiem wielkości liter odrzuciłoby każdą
    paczkę, gdyby zapis w skrypcie i w API się rozjechały, i przycisk „Zaktualizuj"
    przestałby działać wszystkim naraz."""
    assert (
        "$downloadUrl.StartsWith($DownloadPrefix, [StringComparison]::OrdinalIgnoreCase)" in LAUNCHER
    )
    api = re.search(r"^\$HubApi = 'https://api\.github\.com/repos/([^/']+/[^/']+)/releases", LAUNCHER, re.M)
    pobieranie = re.search(
        r"^\$DownloadPrefix = 'https://github\.com/([^/']+/[^/']+)/releases/download/'$", LAUNCHER, re.M
    )
    assert api and pobieranie, "brak adresu API albo prefiksu pobierania"
    assert api.group(1) == pobieranie.group(1) == HUB


def test_start_nie_cofa_wersji():
    """Po aktualizacji z panelu folder ze starą paczką zostaje na dysku. Odpalony
    przez pomyłkę nie może po cichu przywrócić starszej wersji."""
    text = tekst("packaging/start.ps1")
    assert "Get-ImageVersion" in text
    assert "$runningVersion -gt $desiredVersion" in text


def test_start_dziala_pod_helperem_aktualizacji():
    """Helper aktualizacji ustawia $ErrorActionPreference = 'Stop', a uruchomiony przez niego
    start.ps1 tę wartość dziedziczy. Windows PowerShell 5.1 zamienia wtedy wpis dockera na
    stderr (np. „No such object" dla kontenera, którego nie ma) w błąd przerywający, mimo
    2>$null, i instalacja urywa się na pierwszym takim wywołaniu. Skrypt musi sam przywrócić
    'Continue' i sprawdzać $LASTEXITCODE."""
    text = tekst("packaging/start.ps1")
    assert re.search(r"^\$ErrorActionPreference = 'Continue'$", text, re.M)


def test_kontrakt_wydania_jest_ten_sam_w_trzech_miejscach():
    """Repozytorium, prefiks tagu, nazwa pliku i folder w paczce są czytane przez trzy
    programy: workflow (kopiuje wydanie na stronę z pobieraniem), panel (app/updates.py)
    i instalator (update-launcher.ps1). Zmiana w jednym miejscu bez pozostałych psuje
    aktualizację osobom, które już mają program, a dowiedzą się o tym dopiero wtedy, gdy
    przestanie działać.

    Kontrakt: wydania huba Mysttic/Mysttic, tag tunnelbox-v<wersja>, plik
    tunnelbox-<wersja>.zip, a w nim folder tunnelbox-<wersja>/ ze start.ps1.
    """
    panel = (ROOT / "app" / "updates.py").read_text(encoding="utf-8")
    release = job(WORKFLOW, "release")
    site = job(WORKFLOW, "site")

    # repozytorium z wydaniami: hub, na który job site kopiuje paczkę
    assert f'HUB_REPO = "{HUB}"' in panel
    assert f"api.github.com/repos/{HUB}/releases" in LAUNCHER
    assert f"HUB: {HUB}" in site
    assert 'gh release create "$HUB_TAG"' in site
    assert '--repo "$HUB"' in site

    # tag na hubie: tunnelbox-v<wersja>
    assert 'TAG_PREFIX = "tunnelbox-v"' in panel
    assert "PROJECT: tunnelbox" in site
    assert "HUB_TAG: tunnelbox-v${{ needs.version.outputs.version }}" in site
    assert "$TagPrefix = 'tunnelbox-v'" in LAUNCHER
    assert '$tag = "$TagPrefix$version"' in LAUNCHER

    # nazwa paczki: tunnelbox-<wersja>.zip, na stronę trafia bez zmian, prosto z wydania
    # tego repozytorium
    assert 'PKG="tunnelbox-${VERSION}"' in release
    assert "files: dist/tunnelbox-${{ env.VERSION }}.zip" in release
    assert "tag_name: ${{ env.TAG }}" in release
    assert "TAG: ${{ needs.version.outputs.tag }}" in site
    assert 'gh release download "$TAG" --repo "$GITHUB_REPOSITORY"' in site
    assert '--pattern "tunnelbox-$VERSION.zip"' in site
    assert 'gh release create "$HUB_TAG" "copy/$PROJECT-$VERSION.zip"' in site
    assert r'ASSET_RE = re.compile(r"^tunnelbox-\d+\.\d+\.\d+\.zip$")' in panel
    assert '$assetName = "tunnelbox-$version.zip"' in LAUNCHER

    # folder w paczce: tunnelbox-<wersja>/ ze start.ps1 na wierzchu, bo instalator go uruchamia
    assert 'zip -r "$PKG.zip" "$PKG"' in release
    assert re.search(r'^\s*cp [^\n]*packaging/start\.ps1[^\n]* "dist/\$PKG/"$', release, re.M)
    assert '$target = Join-Path $VersionsDir "tunnelbox-$version"' in LAUNCHER
    assert "$start = Join-Path $target 'start.ps1'" in LAUNCHER

    # „Co nowego" w panelu, opis wydania na hubie i komunikaty instalatora: ta sama strona
    assert f'PAGE_URL = "{PAGE}"' in panel
    assert f"SITE: {PAGE}" in site
    assert f"$PageUrl = '{PAGE}'" in LAUNCHER


def test_bez_kopii_na_stronie_wydanie_pada():
    """Bez kopii na hubie strona projektu nie da wydania do pobrania, a zainstalowane
    panele się o nim nie dowiedzą. Brak HUB_TOKEN ma więc wywrócić job
    (i założyć zgłoszenie), a nie przejść po cichu."""
    site = job(WORKFLOW, "site")
    assert re.search(r'if \[ -z "\$\{HUB_TOKEN:-\}" \]; then\n(?:[^\n]*\n){0,3}?\s*exit 1\n', site)


def test_workflow_kasuje_tylko_wydania_tego_projektu():
    """Strona trzyma wydania kilku programów pod jednym repozytorium."""
    assert "PROJECT: tunnelbox" in WORKFLOW
    assert 'grep -E "^$PROJECT-v"' in WORKFLOW


def test_obraz_zawiera_plik_wersji():
    """Panel czyta numer wersji z pliku obok kodu — bez tego pokazywałby „dev"."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY VERSION /app/VERSION" in dockerfile
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert "VERSION" not in dockerignore, "VERSION nie może być wykluczony z kontekstu"


def test_obraz_instaluje_tylko_kola_z_etapu_wheels():
    """Na linux/arm/v7 cffi nie ma gotowego koła na PyPI i kompiluje się ze źródeł, a kompilator
    jest tylko w etapie wheels. Końcowy etap, który sięgnąłby do PyPI, próbowałby na arm/v7
    kompilować bez gcc — a na amd64 nic by tego nie zdradziło."""
    dockerfile = tekst("Dockerfile")
    assert re.search(r"^FROM \S+ AS wheels$", dockerfile, re.M)
    assert "pip3 wheel" in dockerfile
    assert "from=wheels" in dockerfile
    assert "--no-index --find-links /tmp/wheels" in dockerfile


def test_licencje_trafiaja_do_obrazu_i_paczki():
    """Obraz i paczka zawierają programy na GPL (openfortivpn, strongSwan, socat) — razem
    z nimi idzie informacja o licencjach i dokładnych wersjach, po których da się odszukać
    źródła. .dockerignore wyklucza *.md, więc bez wyjątku dla THIRD_PARTY.md COPY
    w Dockerfile przerwałby budowanie obrazu."""
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "THIRD_PARTY.md").is_file()

    dockerfile = tekst("Dockerfile")
    assert "COPY LICENSE THIRD_PARTY.md /usr/share/doc/tunnelbox/" in dockerfile
    assert "> /usr/share/doc/tunnelbox/third-party-versions.txt" in dockerfile

    ignore = tekst(".dockerignore").split()
    assert "LICENSE" not in ignore
    assert "THIRD_PARTY.md" not in ignore
    if "*.md" in ignore:
        # wyjątek działa tylko wtedy, gdy stoi PO wzorcu, który znosi
        assert "!THIRD_PARTY.md" in ignore[ignore.index("*.md"):], "THIRD_PARTY.md wykluczony z kontekstu"

    release = job(WORKFLOW, "release")
    assert 'cp LICENSE THIRD_PARTY.md "dist/$PKG/"' in release
    assert "/usr/share/doc/tunnelbox/third-party-versions.txt" in release
    assert '"dist/$PKG/THIRD_PARTY_VERSIONS.txt"' in release


def test_brak_recznych_skryptow_wlacz_wylacz():
    """Włączanie/wyłączanie odbywa się w panelu — nie ma skryptów do klikania."""
    leftovers = list((ROOT / "packaging").glob("*szybkie-rdp*"))
    assert not leftovers, f"pozostały ręczne skrypty: {[p.name for p in leftovers]}"


PANEL_NAME_URL = "http://tunnelbox.localhost:25263"
PANEL_IP_URL = "http://127.0.0.1:25263"


@pytest.mark.parametrize("compose", COMPOSE_Z_PORTAMI)
def test_panel_ma_wlasny_port(compose):
    """Panel nie może siedzieć na pospolitym 8080 — adres ma być rozpoznawalny.
    Na tym porcie helper aktualizacji sprawdza też, czy nowa wersja wstała."""
    text = (ROOT / compose).read_text(encoding="utf-8")
    assert "127.0.0.1:25263:8080" in text
    assert "127.0.0.1:8080:8080" not in text


@pytest.mark.parametrize("compose", COMPOSE_Z_PORTAMI)
def test_porty_tylko_na_petli_zwrotnej(compose):
    """Kontener jest uprzywilejowany, a panel trzyma hasła do VPN-ów — z sieci ma być
    nieosiągalny; wpis bez adresu („25263:8080") słuchałby na wszystkich interfejsach.
    Pula musi pokrywać się z adresami, które panel przydziela maszynom (local_host
    w app/connections.py) — inaczej przekierowanie danej maszyny „działa", a nic na
    jej adresie nie słucha."""
    wpisy = porty(tekst(compose))
    for wpis in wpisy:
        assert re.fullmatch(r"127\.0\.0\.\d{1,3}:\d+:\d+", wpis), f"port poza pętlą zwrotną: {wpis}"
    pula = [f"{local_host(p)}:{p}:{p}" for p in range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1)]
    assert wpisy == ["127.0.0.1:25263:8080", *pula]


@pytest.mark.parametrize("compose", COMPOSE)
def test_compose_bez_starej_nazwy(compose):
    """Stara nazwa usługi, kontenera albo obrazu to ślad po niedokończonej zmianie nazwy.
    Usługa wszędzie nazywa się tak samo, bo nakładka docker-compose.build.yml nadpisuje ją
    po nazwie."""
    text = tekst(compose)
    assert "fortivpn" not in bez_komentarzy(text).lower()
    assert usluga(text) == "tunnelbox"


def test_compose_z_rejestru():
    """docker-compose.yml w katalogu głównym to instalacja jednym poleceniem dla każdego:
    obraz z GHCR (nazwa wyłącznie małymi literami — inaczej „invalid reference format"),
    bez budowania. TUNNELBOX_INSTALL: registry przełącza pasek aktualizacji w panelu na
    podpowiedź „docker compose pull" — przycisk „Zaktualizuj" ściągnąłby paczkę ZIP obok."""
    kod = bez_komentarzy(tekst("docker-compose.yml"))
    assert "image: ghcr.io/mysttic/tunnelbox:latest" in kod
    assert "container_name: tunnelbox" in kod
    assert "TUNNELBOX_INSTALL: registry" in kod
    assert "build:" not in kod


def test_compose_ze_zrodel_buduje_obraz_lokalnie():
    """Nakładka dla uruchomienia ze źródeł: budowanie z Dockerfile zamiast obrazu z rejestru
    i własny tag tunnelbox:dev — lokalny build nie może podszyć się pod obraz z GHCR."""
    kod = bez_komentarzy(tekst("docker-compose.build.yml"))
    assert re.search(r"^    build: \.$", kod, re.M)
    assert "image: tunnelbox:dev" in kod
    assert "TUNNELBOX_INSTALL: source" in kod


@pytest.mark.parametrize("start", ["start.sh", "start.ps1"])
def test_start_ze_zrodel_uzywa_obu_plikow_compose(start):
    """Ze źródeł panel ma wstać z kodu w repozytorium — sam docker-compose.yml pobrałby
    ghcr.io/mysttic/tunnelbox:latest."""
    text = tekst(start)
    assert "docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build" in text


def test_paczka_uruchamia_obraz_ktory_ma_w_sobie():
    """Compose paczki ma pull_policy: never. Jeśli tag podstawiony za __IMAGE__ różni się od
    tagu obrazu zapisanego w paczce (docker save), albo plik obrazu nazywa się inaczej, niż
    szukają go skrypty startowe, panel nie wstanie u nikogo, kto rozpakował ZIP. Brak
    TUNNELBOX_INSTALL oznacza dla panelu instalację z paczki (przycisk „Zaktualizuj")."""
    kod = bez_komentarzy(tekst("packaging/docker-compose.yml"))
    assert "image: __IMAGE__" in kod
    assert "container_name: tunnelbox" in kod
    assert "pull_policy: never" in kod
    assert "TUNNELBOX_INSTALL" not in kod

    release = job(WORKFLOW, "release")
    assert "VERSION: ${{ needs.version.outputs.version }}" in release
    assert "tags: tunnelbox:${{ env.VERSION }}" in release
    assert 'sed "s#__IMAGE__#tunnelbox:${VERSION}#g" packaging/docker-compose.yml' in release
    assert 'docker save "tunnelbox:${VERSION}" | gzip > "dist/$PKG/tunnelbox-image-${VERSION}.tar.gz"' in release

    ps1 = tekst("packaging/start.ps1")
    sh = tekst("packaging/start.sh")
    assert '-Filter "tunnelbox-image-*.tar.gz"' in ps1
    assert "ls tunnelbox-image-*.tar.gz" in sh
    # stare obrazy sprząta to samo repozytorium, z którego pochodzi obraz paczki, i tylko
    # tagi z numerem wersji: tunnelbox:dev zbudowany ze źródeł zostaje
    assert "$ImageRepository = 'tunnelbox'" in ps1
    assert r"$tag -match ':\d+\.\d+\.\d+$'" in ps1
    assert 'remove_version_tags tunnelbox "$DESIRED"' in sh
    assert "grep -E ':[0-9]+\\.[0-9]+\\.[0-9]+$'" in sh


# Dawna nazwa programu (FortiVPN 2) w kodzie: w adresie panelu, nazwie kontenera, katalogu
# danych, protokole, zmiennej albo repozytorium. Tunnelbox nie przejmuje instalacji sprzed
# zmiany nazwy (to czysta instalacja, połączenia przenosi eksport i import), więc stara
# nazwa nie ma tu żadnego uzasadnionego użycia. openfortivpn to klient SSL-VPN w obrazie.
STARA_NAZWA = re.compile(r"(?<!open)fortivpn", re.I)
KOD = sorted({
    *ROOT.glob("start.*"),
    *ROOT.glob("docker-compose*.yml"),
    ROOT / "entrypoint.sh",
    ROOT / "Dockerfile",
    *(ROOT / "packaging").glob("start.*"),
    *(ROOT / "packaging").glob("*.ps1"),
    ROOT / "packaging" / "docker-compose.yml",
    *(ROOT / "tools").glob("*"),
    *(ROOT / "app").glob("*.py"),
    *(ROOT / "app" / "static").glob("*"),
    *(ROOT / ".github" / "workflows").glob("*.yml"),
})


@pytest.mark.parametrize("plik", KOD, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_kod_bez_starej_nazwy(plik):
    """Pominięta zmiana nazwy w skrypcie wychodzi dopiero u użytkownika — np. przeglądarka
    otwiera stary adres albo compose nie dostaje katalogu danych, bo czyta inną zmienną."""
    text = plik.read_text(encoding="utf-8-sig")
    znalezione = sorted({m.group(0) for m in STARA_NAZWA.finditer(text)})
    assert not znalezione, f"{plik.name}: stara nazwa {znalezione}"


def test_skrypty_otwieraja_nazwe_ale_odpytuja_po_ip():
    """Nazwę *.localhost rozwiązują przeglądarki, ale NIE resolver .NET/PowerShell.
    Przeglądarkę otwieramy więc po nazwie, a panel odpytujemy po adresie IP."""
    ps1 = tekst("packaging/start.ps1")
    assert f'Start-Process "{PANEL_NAME_URL}"' in ps1
    assert f"'{PANEL_IP_URL}/api/vault'" in ps1, "PowerShell musi odpytywać po IP"
    # helper aktualizacji czeka na nową wersję tak samo — po IP
    assert f"$PanelApi = '{PANEL_IP_URL}/api/vault'" in LAUNCHER
    for nazwa, text in [("start.ps1", ps1), ("update-launcher.ps1", LAUNCHER)]:
        for linia in text.splitlines():
            if "Invoke-RestMethod" in linia or "$PanelApi =" in linia:
                assert ".localhost" not in linia, f"{nazwa} odpytuje po nazwie: {linia.strip()}"

    sh = tekst("packaging/start.sh")
    assert f'URL="{PANEL_NAME_URL}"' in sh
    assert f'API="{PANEL_IP_URL}"' in sh
    assert '"$API/api/vault"' in sh


def test_dane_uzytkownika_poza_folderem_programu():
    """Sejf musi leżeć poza paczką — inaczej rozpakowanie nowej wersji obok starej
    startuje z pustą konfiguracją. Katalog trafia do compose przez TUNNELBOX_DATA,
    więc zmienna musi być ustawiona przed docker compose up."""
    compose = tekst("packaging/docker-compose.yml")
    assert '"${TUNNELBOX_DATA:-./data}:/data"' in compose

    ps1 = tekst("packaging/start.ps1")
    assert "$AppHome = Join-Path $env:LOCALAPPDATA 'Tunnelbox'" in ps1
    assert "$DataDir = Join-Path $AppHome 'data'" in ps1
    assert "$env:TUNNELBOX_DATA = " in ps1
    assert ps1.index("$env:TUNNELBOX_DATA = ") < ps1.index("docker compose up -d")

    sh = tekst("packaging/start.sh")
    assert 'DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/tunnelbox/data"' in sh
    assert 'export TUNNELBOX_DATA="$DATA_DIR"' in sh
    assert sh.index("export TUNNELBOX_DATA=") < sh.index("docker compose up -d")


@pytest.mark.parametrize("start", ["packaging/start.ps1", "packaging/start.sh"],
                         ids=["windows", "unix"])
def test_aktualizacja_sprzata_poprzednia_wersje(start):
    """Aktualizacja ma sama usunąć stary kontener i obraz oraz przenieść sejf."""
    text = tekst(start)
    assert "vault.enc" in text, "brak migracji sejfu"
    assert "rm -f" in text, "brak usuwania starego kontenera"
    assert "rmi" in text, "brak usuwania starego obrazu"
    # sprzątanie tylko przy realnej zmianie wersji obrazu
    assert "Config.Image" in text, "brak porównania wersji obrazu"


def test_start_bierze_sejf_najpierw_z_wlasnego_katalogu_danych():
    """Kopia robocza na czas instalacji powstaje z pierwszego znalezionego sejfu. Bieżąca
    konfiguracja musi być pierwsza: inaczej aktualizacja wzięłaby starszy sejf z folderu
    sąsiedniej paczki i nadpisała nim nowszy."""
    kandydaci = funkcja(tekst("packaging/start.ps1"), "Get-VaultCandidates")
    assert kandydaci.index("$dirs += $DataDir") < kandydaci.index("Get-ContainerDataPath $ContainerName")

    petla = next(linia for linia in tekst("packaging/start.sh").splitlines()
                 if linia.startswith("for candidate in "))
    assert petla.startswith('for candidate in "$DATA_DIR" ')


def test_helper_sprzata_tylko_foldery_paczek():
    """Po udanej aktualizacji helper kasuje stare paczki, wyłącznie foldery tunnelbox-X.Y.Z
    we własnym katalogu wersji. Szerszy wzorzec albo inny katalog skasowałby folder, który
    użytkownik sam rozpakował."""
    assert "$VersionsDir = Join-Path $AppHome 'versions'" in LAUNCHER
    assert r"$_.Name -match '^tunnelbox-\d+\.\d+\.\d+$'" in LAUNCHER
    przegladane = [linia.strip() for linia in bez_komentarzy(LAUNCHER).splitlines() if "Get-ChildItem" in linia]
    assert przegladane and all("-LiteralPath $VersionsDir " in linia for linia in przegladane), przegladane


@pytest.mark.parametrize("start", ["start.ps1", "packaging/start.ps1"], ids=["dev", "pakiet"])
def test_start_rejestruje_protokol_rdp(start):
    """Rejestracja protokołu ma dziać się automatycznie przy starcie —
    użytkownik nie powinien uruchamiać niczego ręcznie z konsoli."""
    text = tekst(start)
    assert "Enable-FastRdp" in text
    assert "HKCU:\\Software\\Classes\\tunnelbox-rdp" in text
    assert "rdp-launcher.ps1" in text


def test_obrazy_trafiaja_do_rejestru_na_trzy_architektury():
    """Instalacja z rejestru (docker-compose.yml) ciągnie ghcr.io/mysttic/tunnelbox:latest
    na każdym komputerze: Mac z Apple Silicon i Raspberry Pi potrzebują arm64 i arm/v7.
    Tagi semver biorą wersję jawnie (value=v<wersja>) — push do main nie jest tagiem, więc
    bez tego zostałby sam latest."""
    images = job(WORKFLOW, "images")
    assert re.search(r"^    needs: version$", images, re.M)
    assert "if: needs.version.outputs.publishing == 'true'" in images
    assert "packages: write" in images
    assert "platforms: linux/amd64,linux/arm64,linux/arm/v7" in images
    assert "push: true" in images
    assert re.search(r"type=semver,pattern=\{\{version\}\},value=v\S+", images)
    assert re.search(r"type=semver,pattern=\{\{major\}\}\.\{\{minor\}\},value=v\S+", images)
    assert "type=raw,value=latest" in images

    # dokładnie ten obraz, którego używa compose z rejestru
    compose = bez_komentarzy(tekst("docker-compose.yml"))
    obraz = re.search(r"^    image: (\S+):latest$", compose, re.M).group(1)
    assert obraz == "ghcr.io/mysttic/tunnelbox"
    assert f"GHCR_IMAGE: {obraz}" in images


def test_docker_hub_tylko_z_sekretami():
    """Docker Hub jest dodatkiem: bez sekretów DOCKERHUB_* (albo z wygasłym tokenem)
    logowanie pada. Gdyby siedziało w jobie images, pociągnęłoby za sobą cały job — obraz
    nie trafiłby nawet do GHCR, z którego korzysta compose, a wydanie by nie powstało.
    Dlatego osobny job, który kopiuje gotowe tagi z GHCR i nikt na niego nie czeka."""
    images = job(WORKFLOW, "images")
    assert "DOCKERHUB" not in images
    assert "docker.io" not in images

    hub = job(WORKFLOW, "dockerhub")
    assert "DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}" in hub
    assert "DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}" in hub
    assert "${{ vars.DOCKERHUB_REPOSITORY || 'mysttic/tunnelbox' }}" in hub
    # bez przebudowy — ten sam manifest co w GHCR
    assert 'docker buildx imagetools create "$@" "$GHCR_IMAGE:$VERSION"' in hub
    assert "docker/build-push-action" not in hub

    # wszystko poza sprawdzeniem sekretów działa tylko z nimi
    for krok in kroki(hub)[1:]:
        if krok.lstrip().startswith("- name: Sekrety Docker Hub"):
            continue
        assert "if: steps.enabled.outputs.on == 'true'" in krok, krok
    assert any("peter-evans/dockerhub-description" in krok for krok in kroki(hub))

    # wydanie i kopia na stronie nie czekają na Docker Hub
    for nazwa in ("release", "site"):
        needs = re.search(r"^    needs: (.*)$", job(WORKFLOW, nazwa), re.M).group(1)
        assert "dockerhub" not in needs, nazwa


def test_wydanie_powstaje_po_obrazie_w_rejestrze():
    """Kopia wydania na stronie jest kanałem aktualizacji: panel z rejestru, gdy ją zobaczy,
    każe zrobić docker compose pull. Kopia opublikowana przed obrazem w GHCR (budowa
    na trzy architektury trwa do godziny) kazałaby ściągnąć wersję, której jeszcze nie ma.
    Dlatego release czeka na images, a site na release."""
    for nazwa, poprzedni in [("release", "images"), ("site", "release")]:
        needs = re.search(r"^    needs: \[([^\]]*)\]$", job(WORKFLOW, nazwa), re.M)
        assert needs and poprzedni in {n.strip() for n in needs.group(1).split(",")}, nazwa
    # tag na zbudowanym commicie — release powstaje później, main mógł się w tym czasie ruszyć
    assert "target_commitish: ${{ github.sha }}" in job(WORKFLOW, "release")


@pytest.mark.parametrize("nazwa", ["images", "release", "dockerhub", "site"])
def test_latest_tylko_dla_najnowszego_wydania(nazwa):
    """Ponowne uruchomienie nieudanego przebiegu starszego wydania (Re-run failed jobs,
    gdy wyszła już nowsza wersja) nie może niczego cofnąć: ani latest i X.Y w rejestrze,
    ani „Latest" na GitHubie (na nie wskazują linki /releases/latest), ani kopii na stronie
    (sprzątanie skasowałoby nowszą), ani opisu na Docker Hub. Decyzja zapada
    w każdym z tych jobów, w chwili jego uruchomienia — nie z wyjść innego joba, które
    „Re-run failed jobs" bierze z pierwszego przebiegu."""
    tekst_joba = job(WORKFLOW, nazwa)
    # błąd sieci przy ls-remote przerywa job, zamiast udawać pustą listę tagów
    assert "REMOTE=\"$(git ls-remote --tags --refs origin 'refs/tags/v*')\"" in tekst_joba
    assert "sort -V" in tekst_joba
    if nazwa == "images":
        assert "flavor: latest=false" in tekst_joba
        assert "type=raw,value=latest,enable=${{ steps.newest.outputs.latest }}" in tekst_joba
        assert ",enable=${{ steps.newest.outputs.minor }}" in tekst_joba
    elif nazwa == "release":
        assert "make_latest: ${{ steps.newest.outputs.latest }}" in tekst_joba
    elif nazwa == "dockerhub":
        assert 'if [ "$LATEST" = "true" ]' in tekst_joba
        assert 'if [ "$MINOR" = "true" ]' in tekst_joba
        opis = next(k for k in kroki(tekst_joba) if "peter-evans/dockerhub-description" in k)
        assert "steps.newest.outputs.latest == 'true'" in opis
    else:
        for krok in kroki(tekst_joba):
            if 'gh release create "$HUB_TAG"' in krok or "gh release delete" in krok:
                assert "if: steps.newest.outputs.latest == 'true'" in krok, krok


def test_nieudane_wydanie_zaklada_zgloszenie():
    """Wydanie, które padło w połowie (ZIP jest, a obrazu w rejestrze albo kopii na stronie
    nie ma), ma być widać w Issues — czerwony przebieg w Actions łatwo przeoczyć. Każdy
    job wydania musi być w needs, inaczej jego awaria przejdzie bez zgłoszenia."""
    raport = job(WORKFLOW, "report-failure")
    # job po przekroczeniu timeout-minutes kończy się jako „cancelled", nie „failure"
    assert re.search(r"^    if: failure\(\) \|\| \(!cancelled\(\) && contains\(needs\.\*\.result, 'cancelled'\)\)$",
                     raport, re.M)
    assert "cancelled) FAILED=" in raport
    needs = re.search(r"^    needs: \[([^\]]*)\]$", raport, re.M)
    assert needs, "brak needs w report-failure"
    pilnowane = {nazwa.strip() for nazwa in needs.group(1).split(",")}
    assert {"version", "images", "release", "dockerhub", "site"} <= pilnowane
    assert set(joby(WORKFLOW)) - {"report-failure"} <= pilnowane
    assert "issues: write" in raport
    assert "gh label create release-failed" in raport
    assert "--label release-failed" in raport
    assert 'TITLE="Release v$VERSION failed"' in raport


def test_ci_dziala_przy_kazdym_pr():
    """PR-y przychodzą i do develop (dependabot, gałęzie robocze), i do main. Filtr gałęzi
    albo warunek head_ref == 'develop' przepuściłby część z nich bez testów. Nazwy jobów
    są nazwami checków wymaganych w ochronie gałęzi — po zmianie nazwy wymagany check nigdy
    nie przychodzi i PR-a nie da się scalić."""
    on = re.search(r"^on:\n(.*?)^\S", bez_komentarzy(CI), re.M | re.S)
    assert on, "brak sekcji on: w ci.yml"
    assert re.search(r"^  pull_request:\s*$", on.group(1), re.M)
    assert "branches" not in on.group(1)
    assert "paths" not in on.group(1)
    assert "head_ref" not in bez_komentarzy(CI)
    assert "name: Testy backendu (pytest)" in CI
    assert "name: Testy e2e (Playwright)" in CI


def test_ci_sprawdza_konwencje_commitow():
    """commitlint czyta git log base..head — przy domyślnym płytkim checkoucie nie znajdzie
    commita bazowego i padnie na każdym PR. Bez pliku konfiguracji nie ma żadnych reguł,
    a różne wersje cli i config-conventional potrafią się ze sobą nie dogadać."""
    commits = job(CI, "commits")
    assert "if: github.event_name == 'pull_request'" in commits
    assert "fetch-depth: 0" in commits
    assert 'npx commitlint --from "${{ github.event.pull_request.base.sha }}"' in commits
    wersje = re.findall(r"@commitlint/(?:cli|config-conventional)@(\S+)", commits)
    assert len(wersje) == 2 and len(set(wersje)) == 1, f"wersje commitlint: {wersje}"

    config = json.loads(tekst(".commitlintrc.json"))
    assert config["extends"] == ["@commitlint/config-conventional"]
