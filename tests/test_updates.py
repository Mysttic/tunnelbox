"""Testy sprawdzania aktualizacji (app/updates.py).

Żaden z nich nie rusza sieci — odpowiedź strony wydań jest podstawiana.
"""

import pytest

import updates


@pytest.fixture(autouse=True)
def czysty_cache():
    updates.reset_cache()
    yield
    updates.reset_cache()


def wydanie(version, *, prefix=updates.TAG_PREFIX, assets=None, draft=False,
            prerelease=False, published="2026-09-01T10:00:00Z"):
    if assets is None:
        assets = [f"tunnelbox-{version}.zip"]
    return {
        "tag_name": f"{prefix}{version}",
        "draft": draft,
        "prerelease": prerelease,
        "published_at": published,
        "assets": [
            {
                "name": name,
                "browser_download_url":
                    f"https://github.com/Mysttic/Mysttic/releases/download/{prefix}{version}/{name}",
                "size": 140 * 1024 * 1024,
            }
            for name in assets
        ],
    }


def podstaw(monkeypatch, releases):
    """Podstawia odpowiedź strony wydań i liczy zapytania."""
    licznik = {"n": 0}

    def fake_fetch(url=updates.API_URL):
        licznik["n"] += 1
        if isinstance(releases, Exception):
            raise releases
        return releases

    monkeypatch.setattr(updates, "_fetch", fake_fetch)
    return licznik


# --- numer wersji ---

@pytest.mark.parametrize("tekst,oczekiwane", [
    ("2.8.0", (2, 8, 0)),
    (" 2.8.0 ", (2, 8, 0)),
    ("2.10.3", (2, 10, 3)),
    ("dev", None),
    ("v2.8.0", None),
    ("2.8", None),
    ("", None),
    (None, None),
])
def test_parse_version(tekst, oczekiwane):
    assert updates.parse_version(tekst) == oczekiwane


def test_porownanie_jest_liczbowe_a_nie_tekstowe(monkeypatch):
    """„2.10.0" jest nowsze niż „2.9.0", choć tekstowo wypada odwrotnie."""
    podstaw(monkeypatch, [wydanie("2.10.0")])
    assert updates.check("2.9.0")["available"] is True


# --- wybór wydania ---

def test_bierze_pierwsze_wydanie_z_prefiksem_projektu():
    """Hub trzyma wydania innych programów: mamy je pomijać."""
    lista = [
        wydanie("9.9.9", prefix="chatt-v"),
        wydanie("1.0.3", prefix="wtyczka-yt-v"),
        wydanie("2.8.0"),
        wydanie("2.7.0"),
    ]
    assert updates.pick_release(lista)["tag_name"] == "tunnelbox-v2.8.0"


def test_wydanie_fortivpn2_z_huba_nie_jest_brane_za_wydanie():
    """Stare wydanie FortiVPN 2 na hubie (fortivpn2-v…) to inny program dla panelu: nawet
    z wyższym numerem nie może zostać wzięte za wydanie Tunnelboxa."""
    stare = wydanie("9.9.9", prefix="fortivpn2-v", assets=["fortivpn2-9.9.9.zip"])
    assert updates.pick_release([stare, wydanie("3.0.0")])["tag_name"] == "tunnelbox-v3.0.0"
    assert updates.pick_release([stare]) is None
    # plik pod starą nazwą też nie pasuje do kontraktu
    assert updates.pick_asset(wydanie("3.1.0", assets=["fortivpn2-3.1.0.zip"])) is None


def test_prefiks_bez_numeru_wersji_jest_pomijany():
    """Po prefiksie „tunnelbox-v" musi stać numer wersji: tag w rodzaju „tunnelbox-viewer"
    też się od niego zaczyna."""
    lista = [
        wydanie("iewer-1.0.0"),            # tag: tunnelbox-viewer-1.0.0
        wydanie("3.0.0-rc1"),              # tag: tunnelbox-v3.0.0-rc1
        wydanie("3.0"),                    # tag: tunnelbox-v3.0
        wydanie("2.9.0"),
    ]
    assert updates.pick_release(lista)["tag_name"] == "tunnelbox-v2.9.0"


def test_pomija_szkice_i_wydania_wstepne():
    lista = [
        wydanie("2.9.0", draft=True),
        wydanie("2.8.5", prerelease=True),
        wydanie("2.8.0"),
    ]
    assert updates.pick_release(lista)["tag_name"] == "tunnelbox-v2.8.0"


def test_pomija_tagi_bez_numeru_wersji():
    assert updates.pick_release([wydanie("wstepne")]) is None
    assert updates.pick_release([]) is None
    assert updates.pick_release(None) is None


def test_asset_po_nazwie_a_nie_po_koncowce():
    """Gdyby wydanie niosło sumę kontrolną, przycisk nie może podać pliku .sha256."""
    rel = wydanie("2.8.0", assets=["tunnelbox-2.8.0.zip.sha256", "SHA256SUMS.txt",
                                   "tunnelbox-2.8.0.zip"])
    assert updates.pick_asset(rel)["name"] == "tunnelbox-2.8.0.zip"


def test_brak_pasujacego_pliku():
    assert updates.pick_asset(wydanie("2.8.0", assets=["cos-innego.zip"])) is None


# --- check() ---

def test_nowsza_wersja(monkeypatch):
    podstaw(monkeypatch, [wydanie("2.8.0")])
    wynik = updates.check("2.7.0")
    assert wynik["available"] is True
    assert wynik["latest"] == "2.8.0"
    assert wynik["asset"] == "tunnelbox-2.8.0.zip"
    assert wynik["download"] == (
        "https://github.com/Mysttic/Mysttic/releases/download/tunnelbox-v2.8.0/tunnelbox-2.8.0.zip")
    assert wynik["page"] == updates.PAGE_URL
    assert wynik["ok"] is True


@pytest.mark.parametrize("moja", ["2.8.0", "2.9.0"])
def test_ta_sama_lub_nowsza_wersja_to_brak_aktualizacji(monkeypatch, moja):
    podstaw(monkeypatch, [wydanie("2.8.0")])
    wynik = updates.check(moja)
    assert wynik["available"] is False
    assert wynik["latest"] == "2.8.0"
    assert wynik["ok"] is True


def test_uruchomienie_ze_zrodel_nie_namawia_na_aktualizacje(monkeypatch):
    """Bez rozpoznanego numeru lokalnego („dev") nie ma czego porównywać."""
    podstaw(monkeypatch, [wydanie("2.8.0")])
    wynik = updates.check("dev")
    assert wynik["available"] is False
    assert wynik["latest"] == "2.8.0"


def test_brak_wydan_projektu(monkeypatch):
    podstaw(monkeypatch, [wydanie("9.9.9", prefix="chatt-v")])
    wynik = updates.check("2.7.0")
    assert (wynik["latest"], wynik["available"], wynik["ok"]) == (None, False, True)


def test_blad_sieci_jest_cichy(monkeypatch):
    podstaw(monkeypatch, OSError("brak sieci"))
    wynik = updates.check("2.7.0")
    assert wynik["ok"] is False
    assert wynik["available"] is False
    assert wynik["current"] == "2.7.0"


def test_zepsuta_odpowiedz_nie_wywraca_panelu(monkeypatch):
    podstaw(monkeypatch, {"message": "API rate limit exceeded"})
    wynik = updates.check("2.7.0")
    assert wynik["ok"] is True          # odpowiedź przyszła, tylko nic w niej nie ma
    assert wynik["latest"] is None


# --- pamięć podręczna ---

def test_pyta_raz_na_dobe(monkeypatch):
    licznik = podstaw(monkeypatch, [wydanie("2.8.0")])
    updates.check("2.7.0")
    updates.check("2.7.0")
    updates.check("2.7.0")
    assert licznik["n"] == 1, "limit bez logowania to 60 zapytań na godzinę na adres IP"


def test_sprawdz_teraz_pomija_cache(monkeypatch):
    licznik = podstaw(monkeypatch, [wydanie("2.8.0")])
    updates.check("2.7.0")
    updates.check("2.7.0", force=True)
    assert licznik["n"] == 2


def test_po_awarii_zostaje_ostatni_znany_wynik(monkeypatch):
    podstaw(monkeypatch, [wydanie("2.8.0")])
    updates.check("2.7.0")
    podstaw(monkeypatch, OSError("brak sieci"))
    wynik = updates.check("2.7.0", force=True)
    assert wynik["latest"] == "2.8.0"
    assert wynik["available"] is True


def test_zmiana_wersji_lokalnej_uniewaznia_cache(monkeypatch):
    """Po aktualizacji panel ma od razu przestać pokazywać pasek."""
    licznik = podstaw(monkeypatch, [wydanie("2.8.0")])
    assert updates.check("2.7.0")["available"] is True
    assert updates.check("2.8.0")["available"] is False
    assert licznik["n"] == 2


# --- kontrakt z repozytorium wydań ---

def test_panel_pyta_hub():
    """Wydania dla wszystkich są na hubie Mysttic/Mysttic, obok wydań innych programów,
    a odróżnia je prefiks tagu."""
    assert updates.HUB_REPO == "Mysttic/Mysttic"
    assert updates.API_URL == (
        "https://api.github.com/repos/Mysttic/Mysttic/releases?per_page=100")
    assert updates.TAG_PREFIX == "tunnelbox-v"
    assert updates.PAGE_URL == "https://mysttic.github.io/Mysttic/tunnelbox/"
    # lista + filtr po prefiksie, a nie /releases/latest (to wydanie dowolnego programu)
    assert "/releases/latest" not in updates.API_URL


def test_zapytanie_przedstawia_sie_nazwa_panelu(monkeypatch):
    """GitHub odrzuca zapytania bez User-Agent."""
    zapamietane = {}

    class Odpowiedz:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(request, timeout):
        zapamietane["request"] = request
        return Odpowiedz()

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    assert updates._fetch() == []
    request = zapamietane["request"]
    assert request.full_url == updates.API_URL
    assert request.get_header("User-agent") == "Tunnelbox-Panel"
