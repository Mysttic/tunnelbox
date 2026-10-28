"""Sprawdzanie, czy jest nowsza wersja panelu.

Wydania dla wszystkich publikuje repozytorium-hub Mysttic/Mysttic, czyli strona
z pobieraniem (https://mysttic.github.io/Mysttic/), i tylko tam pytają zainstalowane panele.
Hub trzyma wydania kilku programów naraz i rozróżnia je prefiks tagu. Paczkę każdego wydania
kopiuje tam job „site" w .github/workflows/release.yml.

Kontrakt: tag z prefiksem projektu i nazwa pliku niosąca wersję.

    tag:  tunnelbox-v3.0.0
    plik: tunnelbox-3.0.0.zip

Bierzemy listę wydań i filtrujemy po prefiksie tagu, zamiast pytać o /releases/latest:
„latest" huba to najnowsze wydanie dowolnego programu, a szkice i wydania wstępne
pomijamy tak samo jak strona projektu. Zmiana prefiksu albo nazwy pliku psuje
aktualizacje wszystkim, którzy mają już zainstalowaną aplikację, a dowiedzą się o tym
dopiero wtedy, gdy przestanie działać. Pilnuje tego test tests/test_packaging.py.

Każdy błąd (brak sieci, timeout, inny kształt odpowiedzi, limit zapytań) kończy się
wpisem w logu, a panel działa dalej.
"""

import json
import logging
import re
import time
import urllib.error
import urllib.request

log = logging.getLogger("tunnelbox.updates")

# hub z wydaniami wszystkich programów; 100 na stronę, tak jak czyta je strona z pobieraniem,
# żeby wydanie tego programu nie wypadło poza pierwszą stronę, gdy na hubie przybędzie innych
HUB_REPO = "Mysttic/Mysttic"
TAG_PREFIX = "tunnelbox-v"
ASSET_RE = re.compile(r"^tunnelbox-\d+\.\d+\.\d+\.zip$")
PAGE_URL = "https://mysttic.github.io/Mysttic/tunnelbox/"
API_URL = f"https://api.github.com/repos/{HUB_REPO}/releases?per_page=100"

TIMEOUT = 6          # sekundy na odpowiedź API
OK_TTL = 24 * 3600   # udane sprawdzenie: raz na dobę (limit bez logowania to 60/h na IP)
FAIL_TTL = 3600      # nieudane: spróbuj za godzinę, a nie za dobę

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# ostatni wynik: {"result": dict, "until": float}
_cache: dict = {}


def parse_version(text: str):
    """„2.8.0" -> (2, 8, 0). Cokolwiek innego (np. „dev") -> None."""
    m = VERSION_RE.match((text or "").strip())
    return tuple(int(g) for g in m.groups()) if m else None


def _fetch(url: str = API_URL):
    """Lista wydań repozytorium. Rzuca wyjątkiem — obsługa jest w check()."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            # GitHub odrzuca zapytania bez User-Agent
            "User-Agent": "Tunnelbox-Panel",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def pick_release(releases):
    """Najnowsze wydanie panelu z listy wydań (pierwsze pasujące).

    Szkice i wydania wstępne pomijamy, tak samo jak strona projektu.
    """
    for release in releases or []:
        if not isinstance(release, dict):
            continue
        if release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name") or ""
        if not tag.startswith(TAG_PREFIX):
            continue
        if parse_version(tag[len(TAG_PREFIX):]) is None:
            continue
        return release
    return None


def pick_asset(release):
    """Plik paczki z wydania — po nazwie, bo tylko ona jest częścią kontraktu."""
    for asset in release.get("assets") or []:
        if isinstance(asset, dict) and ASSET_RE.match(asset.get("name") or ""):
            return asset
    return None


def empty(current: str) -> dict:
    return {
        "current": current,
        "latest": None,
        "available": False,
        "asset": None,
        "download": None,
        "size": None,
        "published_at": None,
        "page": PAGE_URL,
        "checked_at": None,
        "ok": False,
    }


def _describe(current: str, release, asset) -> dict:
    result = empty(current)
    result["ok"] = True
    result["checked_at"] = time.time()
    if not release:
        return result

    latest = release["tag_name"][len(TAG_PREFIX):]
    here = parse_version(current)
    result["latest"] = latest
    result["published_at"] = release.get("published_at")
    # bez rozpoznanej wersji lokalnej (uruchomienie ze źródeł — „dev") nie ma czego
    # porównywać; numer z GitHuba pokazujemy, ale do aktualizacji nie namawiamy
    result["available"] = bool(here and parse_version(latest) > here)
    if asset:
        result["asset"] = asset.get("name")
        result["download"] = asset.get("browser_download_url")
        result["size"] = asset.get("size")
    return result


def check(current: str, force: bool = False) -> dict:
    """Wynik sprawdzenia — z pamięci podręcznej albo świeży.

    force=True pomija pamięć podręczną (przycisk „Sprawdź teraz").
    """
    now = time.time()
    cached = _cache.get("entry")
    if not force and cached and cached["until"] > now and cached["result"]["current"] == current:
        return cached["result"]

    try:
        releases = _fetch()
        release = pick_release(releases)
        asset = pick_asset(release) if release else None
        if release and not asset:
            log.info("Wydanie %s nie ma pliku paczki — pomijam.", release.get("tag_name"))
        result = _describe(current, release, asset)
        ttl = OK_TTL
    except (urllib.error.URLError, OSError, ValueError, TypeError, KeyError) as e:
        log.info("Nie udało się sprawdzić aktualizacji: %s", e)
        result = empty(current)
        # ostatni znany wynik zostaje na ekranie — nowe sprawdzenie za godzinę
        if cached and cached["result"]["ok"]:
            result = dict(cached["result"])
        ttl = FAIL_TTL

    _cache["entry"] = {"result": result, "until": now + ttl}
    return result


def reset_cache() -> None:
    """Czyści pamięć podręczną (testy, zmiana ustawień)."""
    _cache.clear()
