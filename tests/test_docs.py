"""Testy instrukcji obsługi — pilnują, żeby dokumentacja nie rozjechała się z panelem.

Instrukcja jest dwujęzyczna: docs/MANUAL.md (angielski, domyślny język panelu) i
docs/MANUAL.pl.md. Każda pokazuje zrzuty ze swojego katalogu — docs/img/en i docs/img/pl —
a generuje je `node tools/screenshots.js`. Testy sprawdzają, czy komplet się zgadza:
każdy zrzut istnieje, żaden nie leży bezużytecznie, generator zna wszystkie, obie wersje
mają te same sekcje, a spis treści pasuje do nagłówków.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).parent.parent
IMG = ROOT / "docs" / "img"
GENERATOR = ROOT / "tools" / "screenshots.js"

WERSJE = {
    "en": ROOT / "docs" / "MANUAL.md",
    "pl": ROOT / "docs" / "MANUAL.pl.md",
}
TEKST = {jezyk: plik.read_text(encoding="utf-8") for jezyk, plik in WERSJE.items()}


def uzyte(jezyk: str) -> list[str]:
    """Nazwy zrzutów pokazywanych w danej wersji instrukcji."""
    return re.findall(rf"!\[[^\]]*\]\(img/{jezyk}/([^)]+)\)", TEKST[jezyk])


def sekcje(jezyk: str) -> list[tuple[str, str]]:
    return re.findall(r"^## (\d+)\. (.+)$", TEKST[jezyk], re.M)


@pytest.mark.parametrize("jezyk", list(WERSJE))
def test_zrzuty_uzyte_w_instrukcji_istnieja(jezyk):
    brak = [nazwa for nazwa in uzyte(jezyk) if not (IMG / jezyk / nazwa).is_file()]
    assert not brak, f"instrukcja ({jezyk}) pokazuje nieistniejące pliki: {brak}"


@pytest.mark.parametrize("jezyk", list(WERSJE))
def test_kazdy_zrzut_ma_swoje_miejsce(jezyk):
    """Zrzut, którego nikt nie pokazuje, to zwykle ślad po starej wersji panelu."""
    osierocone = sorted(p.name for p in (IMG / jezyk).glob("*.png") if p.name not in uzyte(jezyk))
    assert not osierocone, f"nieużywane zrzuty ({jezyk}): {osierocone}"


def test_zrzuty_leza_tylko_w_katalogach_jezykow():
    """Po podziale na języki w docs/img nie ma już luźnych plików — zostawione
    myliłyby przy następnym odświeżeniu, bo generator ich nie nadpisuje."""
    luzne = sorted(p.name for p in IMG.glob("*.png"))
    assert not luzne, f"zrzuty poza katalogiem języka: {luzne}"


def test_obie_wersje_pokazuja_ten_sam_komplet():
    """Instrukcje mają się różnić językiem, a nie zawartością."""
    assert uzyte("en") == uzyte("pl")


def test_generator_zna_wszystkie_zrzuty():
    """Bez tego `node tools/screenshots.js` odświeżyłby tylko część obrazków,
    a reszta zostałaby z poprzedniej wersji interfejsu."""
    src = GENERATOR.read_text(encoding="utf-8")
    generowane = {f"{m}.png" for m in re.findall(r'nazwa: "([^"]+)"', src)}
    assert set(uzyte("en")) <= generowane, f"generator nie robi: {sorted(set(uzyte('en')) - generowane)}"
    assert 'const JEZYKI = ["en", "pl"];' in src, "generator musi robić zrzuty w obu językach"


@pytest.mark.parametrize("jezyk", list(WERSJE))
def test_spis_tresci_zgadza_sie_z_naglowkami(jezyk):
    naglowki = sekcje(jezyk)
    spis = re.findall(r"^(\d+)\. \[([^\]]+)\]\(#", TEKST[jezyk], re.M)
    assert spis == naglowki, f"spis treści ({jezyk}) nie odpowiada nagłówkom sekcji"
    assert [int(n) for n, _ in naglowki] == list(range(1, len(naglowki) + 1)), (
        "numeracja sekcji ma dziurę albo powtórzenie"
    )


def test_obie_wersje_maja_te_same_sekcje():
    """Numeracja musi się zgadzać — odsyłacze w tekście wskazują na numery sekcji."""
    assert [n for n, _ in sekcje("en")] == [n for n, _ in sekcje("pl")]


@pytest.mark.parametrize("jezyk, hasla", [
    ("en", ["IPsec", "Check for updates", "Fast RDP connect", "Export configuration",
            "Import configuration", "Add machine", "Language"]),
    ("pl", ["IPsec", "Sprawdzaj aktualizacje", "Szybkie łączenie RDP",
            "Eksportuj konfigurację", "Importuj konfigurację", "Dodaj maszynę", "Język"]),
])
def test_instrukcja_opisuje_biezace_funkcje(jezyk, hasla):
    """Lista rzeczy, o których instrukcja milczała, gdy panel już je miał."""
    for haslo in hasla:
        assert haslo in TEKST[jezyk], f"instrukcja ({jezyk}) nie wspomina o: {haslo}"


def test_wersje_odsylaja_do_siebie():
    assert "MANUAL.pl.md" in TEKST["en"], "wersja angielska nie linkuje do polskiej"
    assert "MANUAL.md" in TEKST["pl"], "wersja polska nie linkuje do angielskiej"


def test_dokumentacja_idzie_do_paczki():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "docs/MANUAL.md docs/MANUAL.pl.md" in workflow
    assert "docs/img" in workflow
    assert "packaging/INSTALL.md" in workflow
    assert "packaging/INSTALL.pl.md" in workflow


def test_readme_ma_obie_wersje():
    en = (ROOT / "README.md").read_text(encoding="utf-8")
    pl = (ROOT / "README.pl.md").read_text(encoding="utf-8")
    assert "README.pl.md" in en and "README.md" in pl
    assert "docs/MANUAL.md" in en and "docs/MANUAL.pl.md" in pl


# Instalacja jednym poleceniem z pierwszego ekranu README — ta sama w obu językach.
KOMENDA_REJESTRU = (
    "curl -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml"
    " && docker compose up -d"
)


@pytest.mark.parametrize("plik, dawniej, niezwiazany", [
    ("README.md", "formerly fortivpn 2", "not affiliated"),
    ("README.pl.md", "dawniej fortivpn 2", "niezwiązany"),
])
def test_readme_po_zmianie_nazwy(plik, dawniej, niezwiazany):
    """Pierwszy ekran po zmianie nazwy: nota o dawnej nazwie i o braku związku
    z Fortinetem, instalacja jednym poleceniem z rejestru i żadnej wzmianki
    o nieistniejącym katalogu legacy/."""
    tekst = (ROOT / plik).read_text(encoding="utf-8")
    male = tekst.lower()
    assert dawniej in male, f"{plik} nie wspomina o dawnej nazwie"
    assert niezwiazany in male, f"{plik} nie mówi, że projekt nie jest związany z Fortinetem"
    assert KOMENDA_REJESTRU in tekst, f"{plik} nie podaje instalacji z rejestru"
    assert "legacy/" not in male, f"{plik} wspomina o nieistniejącym katalogu legacy/"


def test_readme_ma_sekcje_o_trybie_uprzywilejowanym():
    """SECURITY.md (README.md#why-the-container-is-privileged) i komentarz
    w docker-compose.yml odsyłają do tej sekcji po nazwie."""
    en = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(r"^#+ Why the container is privileged$", en, re.M)


def test_readme_miesci_sie_w_opisie_docker_hub():
    """release.yml wysyła README.md jako opis repozytorium na Docker Hub, a ten przyjmuje
    pełny opis do 25 000 bajtów — dłuższy zostałby ucięty."""
    assert len((ROOT / "README.md").read_bytes()) < 25_000


@pytest.mark.parametrize("plik", ["README.md", "README.pl.md"])
def test_readme_linkuje_tylko_istniejace_pliki(plik):
    """Względne linki i obrazki README (zrzut na pierwszym ekranie, LICENSE, SECURITY.md…)
    muszą wskazywać pliki z repozytorium — także dlatego, że Docker Hub dostaje je
    przepisane na pełne adresy w repozytorium."""
    tekst = (ROOT / plik).read_text(encoding="utf-8")
    cele = re.findall(r"\]\(([^)\s]+)\)", tekst)
    brak = [cel for cel in cele
            if not re.match(r"[a-z]+:|#", cel) and not (ROOT / cel.split("#")[0]).exists()]
    assert not brak, f"{plik} linkuje do nieistniejących plików: {brak}"
