"""Testy dwujęzyczności panelu (angielski domyślnie, polski do wyboru).

Katalogi tłumaczeń łatwo rozjeżdżają się po cichu: ktoś dokłada tekst po angielsku
i zapomina o polskim albo zostawia klucz, którego nikt już nie używa. Te testy
pilnują obu katalogów — frontendu (app/static/i18n.js) i backendu (app/i18n.py).
"""

import pathlib
import re

import pytest

import i18n

ROOT = pathlib.Path(__file__).parent.parent
I18N_JS = (ROOT / "app" / "static" / "i18n.js").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")

# Klucze składane w kodzie (t(`status.${...}`)) — nie da się ich znaleźć wprost.
PREFIKSY_DYNAMICZNE = ("status.", "field.")


def _blok_js(jezyk: str) -> str:
    """Fragment i18n.js z katalogiem jednego języka."""
    start = I18N_JS.index(f"\n  {jezyk}: {{")
    koniec = I18N_JS.index("\n  },", start)
    return I18N_JS[start:koniec]


def _wpisy_js(jezyk: str) -> dict[str, str]:
    """Klucz -> surowy tekst wartości (może być sklejony z kilku linii)."""
    blok = _blok_js(jezyk)
    pozycje = [(m.group(1), m.start(), m.end()) for m in re.finditer(r'"([\w.]+)":', blok)]
    wpisy = {}
    for i, (klucz, _, koniec) in enumerate(pozycje):
        nast = pozycje[i + 1][1] if i + 1 < len(pozycje) else len(blok)
        wpisy[klucz] = blok[koniec:nast]
    return wpisy


JS = {jezyk: _wpisy_js(jezyk) for jezyk in ("en", "pl")}
PY = i18n.MESSAGES


def _pola(tekst: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", tekst))


# --- oba katalogi mają te same klucze ---

def test_frontend_ma_komplet_tlumaczen():
    brak_pl = sorted(set(JS["en"]) - set(JS["pl"]))
    brak_en = sorted(set(JS["pl"]) - set(JS["en"]))
    assert not brak_pl, f"brak polskich tekstów: {brak_pl}"
    assert not brak_en, f"brak angielskich tekstów: {brak_en}"


def test_backend_ma_komplet_tlumaczen():
    brak_pl = sorted(set(PY["en"]) - set(PY["pl"]))
    brak_en = sorted(set(PY["pl"]) - set(PY["en"]))
    assert not brak_pl, f"brak polskich komunikatów: {brak_pl}"
    assert not brak_en, f"brak angielskich komunikatów: {brak_en}"


@pytest.mark.parametrize("katalog", ["frontend", "backend"])
def test_te_same_pola_w_obu_jezykach(katalog):
    """Tekst z {version} po angielsku i bez niego po polsku = dziura w komunikacie."""
    en, pl = (JS["en"], JS["pl"]) if katalog == "frontend" else (PY["en"], PY["pl"])
    rozjazd = {k: (_pola(en[k]), _pola(pl[k])) for k in en if _pola(en[k]) != _pola(pl.get(k, ""))}
    assert not rozjazd, f"różne pola w tekstach: {rozjazd}"


# --- katalog pokrywa to, czego używa kod ---

def _uzyte_w_js() -> set[str]:
    klucze = set(re.findall(r'\bt\(\s*"([\w.]+)"', APP_JS))
    # t(warunek ? "a" : "b") — używane są obie gałęzie
    for para in re.findall(r'\bt\([^)\n]*?\?\s*"([\w.]+)"\s*:\s*"([\w.]+)"', APP_JS):
        klucze |= set(para)
    klucze |= set(re.findall(r'data-i18n(?:-html|-ph|-title|-aria)?="([\w.]+)"', INDEX_HTML))
    return klucze


def test_frontend_zna_wszystkie_uzywane_klucze():
    brak = sorted(k for k in _uzyte_w_js() if k not in JS["en"])
    assert not brak, f"panel używa kluczy, których nie ma w katalogu: {brak}"


def test_backend_zna_wszystkie_uzywane_klucze():
    uzyte = set()
    for plik in ("main.py", "vault.py", "connections.py", "ipsec.py"):
        src = (ROOT / "app" / plik).read_text(encoding="utf-8")
        uzyte |= set(re.findall(r'\b(?:i18n\.)?t\(\s*"([\w.]+)"', src))
    # ipsec.py trzyma w tabeli same klucze, bez wywołania t() w miejscu
    uzyte |= set(re.findall(r'^\s+"(ipsec\.[\w.]+)"\),',
                            (ROOT / "app" / "ipsec.py").read_text(encoding="utf-8"), re.M))
    brak = sorted(k for k in uzyte if k not in PY["en"])
    assert not brak, f"backend używa kluczy, których nie ma w katalogu: {brak}"


def test_brak_nieuzywanych_kluczy_frontendu():
    """Zostawiony klucz to zwykle ślad po usuniętym tekście — i mylący ślad."""
    uzyte = _uzyte_w_js()
    zbedne = sorted(k for k in JS["en"]
                    if k not in uzyte and not k.startswith(PREFIKSY_DYNAMICZNE))
    assert not zbedne, f"nieużywane klucze: {zbedne}"


# --- domyślny język ---

def test_domyslny_jezyk_to_angielski():
    assert i18n.DEFAULT_LANG == "en"
    assert 'const DEFAULT_LANG = "en";' in I18N_JS
    assert '<html lang="en">' in INDEX_HTML


def test_t_wraca_do_angielskiego_i_nie_wywraca_sie(mowi_po):
    mowi_po("pl")
    assert i18n.t("vault.badPassword") == PY["pl"]["vault.badPassword"]
    assert i18n.t("nie.ma.takiego.klucza") == "nie.ma.takiego.klucza"
    assert i18n.t("api.portTaken", port=13391).endswith("13391 jest już zajęty.")


def test_nieznany_jezyk_nie_zmienia_ustawienia(mowi_po):
    mowi_po("pl")
    assert i18n.set_lang("de") == "pl"
