"""Higiena repozytorium: w śledzonych plikach nie ma prawdziwych adresów publicznych.

Prawdziwy adres, np. bramy VPN klienta wklejony jako przykład do podpowiedzi formularza
albo do testu, nie może trafić do publicznego repozytorium. Przykłady biorą adresy z pul
dokumentacyjnych (RFC 5737: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), prywatnych
albo loopback, a hosty z przykładowych domen. Publiczny adres przechodzi tylko z listy
DOZWOLONE.
"""

import ipaddress
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).parent.parent

# Publiczne adresy obecne celowo: resolwery DNS wpisywane do resolv.conf tunelu
# (app/connections.py) i umowne adresy w testach walidacji i logów charona.
DOZWOLONE = {"1.1.1.1", "8.8.8.8", "1.2.3.4", "5.6.7.8"}

# cztery liczby z kropkami, ale nie kawałek dłuższego ciągu (np. numeru wersji 1.2.3.4.5);
# kropka kończąca zdanie nie przeszkadza
IPV4 = re.compile(r"(?<!\d)(?<!\d\.)(?:\d{1,3}\.){3}\d{1,3}(?!\.?\d)")


def sledzone_pliki():
    try:
        wynik = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                               capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("test wymaga kopii repozytorium git")
    return [ROOT / p for p in wynik.stdout.decode("utf-8").split("\0") if p]


def test_w_repozytorium_nie_ma_publicznych_adresow_ip():
    znalezione = []
    for plik in sledzone_pliki():
        if not plik.is_file():
            continue
        dane = plik.read_bytes()
        if b"\0" in dane:  # pliki binarne, np. zrzuty ekranu
            continue
        for nr, linia in enumerate(dane.decode("utf-8", "replace").splitlines(), 1):
            for adres in IPV4.findall(linia):
                try:
                    ip = ipaddress.IPv4Address(adres)
                except ValueError:  # oktet ponad 255 albo zero wiodące
                    continue
                if ip.is_global and not ip.is_multicast and adres not in DOZWOLONE:
                    znalezione.append(f"{plik.relative_to(ROOT).as_posix()}:{nr}: {adres}")
    assert not znalezione, (
        "Publiczne adresy IP w repozytorium. W przykładach użyj 192.0.2.0/24, "
        "198.51.100.0/24 albo 203.0.113.0/24:\n" + "\n".join(znalezione))
