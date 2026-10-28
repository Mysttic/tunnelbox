# Tunnelbox

*[🇬🇧 English](README.md) · 🇵🇱 Polski*

[![Release](https://img.shields.io/github/v/release/Mysttic/tunnelbox)](https://github.com/Mysttic/tunnelbox/releases/latest)
[![CI](https://github.com/Mysttic/tunnelbox/actions/workflows/ci.yml/badge.svg)](https://github.com/Mysttic/tunnelbox/actions/workflows/ci.yml)
[![Licencja: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Docker pulls](https://img.shields.io/docker/pulls/mysttic/tunnelbox)](https://hub.docker.com/r/mysttic/tunnelbox)

Tunnelbox łączy Cię z kilkoma VPN-ami Fortinet (FortiGate) naraz — SSL-VPN i IPsec —
prosto z przeglądarki, a tunele działają w kontenerze Docker, więc Twój komputer nie
zostaje wpięty do sieci klienta.

![Tunnelbox z kilkoma połączeniami naraz](docs/img/pl/12-kilka-polaczen.png)

```sh
curl -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml && docker compose up -d
```

Potem otwórz [http://tunnelbox.localhost:25263](http://tunnelbox.localhost:25263). Na Macu
najpierw dodaj [aliasy pętli zwrotnej](#macos-aliasy-pętli-zwrotnej).

Dawniej FortiVPN 2. Projekt niezwiązany z firmą Fortinet i przez nią niepopierany. Zbudowany
na [openfortivpn](https://github.com/adrienverge/openfortivpn) i
[strongSwanie](https://www.strongswan.org/).

## Dlaczego nie FortiClient albo openfortivpn?

- **Kilka tuneli naraz** — każde połączenie działa we własnej przestrzeni sieciowej, więc
  sieci różnych klientów (nawet o identycznych adresach IP) nie kolidują ze sobą. SSL-VPN
  i IPsec można mieszać dowolnie.
- **Twoja sieć nie wchodzi do sieci klienta** — tunel żyje w przestrzeni sieciowej wewnątrz
  kontenera, a nie na Twoim komputerze. Trasy, DNS i reszta ruchu zostają bez zmian; do
  maszyn za VPN-em łączysz się lokalnie, np. RDP na `127.0.0.3:13392`.
- **Osobny adres pętli zwrotnej na maszynę** — Windows zapamiętuje hasła RDP per adres, bez
  portu, więc przy osobnym adresie „Zapamiętaj mnie" działa dla każdej maszyny, zamiast
  zapisane hasła nadpisywały się nawzajem.
- **Nic nie instaluje się w systemie** — żadnych sterowników, systemowych profili VPN ani
  zmian w ustawieniach sieci. Wystarczy Docker.
- **Wszystko w przeglądarce** — zaszyfrowane zapisane profile, pytanie o token, gdy brama go
  wymaga, nowy certyfikat bramy akceptowany jednym kliknięciem. Panel mówi **domyślnie po
  angielsku, a po polsku na życzenie** — jedno ustawienie obejmuje cały interfejs razem
  z komunikatami połączeń.

## Instalacja

### 1. Docker Compose z rejestru (zalecane)

Potrzebujesz [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows,
Mac) albo Docker Engine z wtyczką Compose (Linux). W folderze, w którym Tunnelbox ma trzymać
dane, uruchom:

```sh
curl -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml && docker compose up -d
```

i otwórz [http://tunnelbox.localhost:25263](http://tunnelbox.localhost:25263). Windows
PowerShell 5.1 (wbudowany w Windows) potrzebuje `curl.exe` zamiast `curl`, który jest tam
aliasem, a oba polecenia trzeba uruchomić osobno, bo `&&` działa dopiero w PowerShell 7:

```powershell
curl.exe -fsSLO https://raw.githubusercontent.com/Mysttic/tunnelbox/main/docker-compose.yml
docker compose up -d
```

- **Dane** leżą w `./data` obok `docker-compose.yml`.
- **Aktualizacja:** `docker compose pull`, a potem `docker compose up -d`, w tym samym
  folderze. Gdy wyjdzie nowa wersja, pasek aktualizacji w panelu pokaże te dwa polecenia —
  wydanie pojawia się dopiero wtedy, gdy jego obraz jest już w GHCR
  (`ghcr.io/mysttic/tunnelbox`, tego używa `docker-compose.yml`); kopia na Docker Hub idzie
  za nim i może się spóźnić, jeśli kopiowanie się nie uda.
- **Obrazy:** `ghcr.io/mysttic/tunnelbox` (GHCR) i `mysttic/tunnelbox` (Docker Hub) dla
  `linux/amd64`, `linux/arm64` i `linux/arm/v7`, z tagami `latest`, `X.Y.Z` i `X.Y`. Żeby
  przypiąć wersję, zmień `:latest` w `docker-compose.yml`.
- **Na Windows** ta droga nie uruchamia `start.bat`, więc szybkie łączenie RDP i aktualizacja
  jednym kliknięciem nie są skonfigurowane — panel zaproponuje wtedy „Pobierz plik .rdp"
  (wyłącz ⚙ Ustawienia → Szybkie łączenie RDP, żeby dostać go od razu). Chcesz obu funkcji?
  Użyj paczki ZIP opisanej niżej.

### 2. Paczka ZIP offline

Pobierz `tunnelbox-X.Y.Z.zip` ze
[strony projektu](https://mysttic.github.io/Mysttic/tunnelbox/) i rozpakuj w dowolnym
folderze. Paczka zawiera gotowy obraz (`tunnelbox-image-X.Y.Z.tar.gz`): skrypt
startowy wczytuje go lokalnie (`docker load`), więc nic nie budujesz ani nie pobierasz
z rejestru.

- **Windows** — kliknij dwukrotnie `start.bat`. Konfiguruje też szybkie łączenie RDP
  i przycisk „⬆️ Zaktualizuj" w panelu. Dane: `%LOCALAPPDATA%\Tunnelbox\data`.
- **Mac/Linux** — uruchom `./start.sh`. Dane: `~/.local/share/tunnelbox/data`.

Panel otworzy się pod adresem
[http://tunnelbox.localhost:25263](http://tunnelbox.localhost:25263) i od tej pory startuje
razem z Dockerem — nie trzeba trzymać otwartego terminala. Paczka ma własne krótkie README
z instalacją i rozwiązywaniem problemów.

### 3. Ze źródeł

```sh
git clone https://github.com/Mysttic/tunnelbox.git
cd tunnelbox
./start.sh        # Windows: dwuklik start.bat
```

`start.bat` / `./start.sh` budują obraz lokalnie (`tunnelbox:dev`, nakładką
`docker-compose.build.yml` na `docker-compose.yml`); pierwsze uruchomienie trwa kilka minut.
Dane leżą w `./data` w repozytorium.

### macOS: aliasy pętli zwrotnej

Przekierowane porty słuchają na `127.0.0.2`–`127.0.0.60`, a macOS domyślnie kieruje na pętlę
zwrotną tylko `127.0.0.1`: Docker Desktop na Maca potrzebuje aliasów `127.0.0.2`–`127.0.0.60`
na `lo0`, inaczej kontener nie wystartuje. `./start.sh` (z paczki i ze źródeł) dodaje
brakujące przez `sudo`. Przy instalacji z rejestru dodaj je sam przed `docker compose up -d`:

```sh
for i in $(seq 2 60); do sudo ifconfig lo0 alias 127.0.0.$i up; done
```

Aliasy znikają po restarcie komputera, a Docker nie uruchomi wtedy kontenera sam: uruchom
pętlę ponownie, a potem `docker compose up -d` w folderze z `docker-compose.yml` (paczka
i źródła: wystarczy `./start.sh`, który robi oba kroki). Linux i Windows niczego takiego nie
potrzebują.

### Podman i Rancher Desktop

Podman i Rancher Desktop nie są jeszcze przetestowane — kontener potrzebuje silnika
działającego jako root (rootful), bo pracuje w trybie uprzywilejowanym z przestrzeniami
sieciowymi i `/dev/ppp` (Podman: `podman machine set --rootful`; Rancher Desktop z silnikiem
dockerd (moby) zachowuje się jak Docker).

## Dlaczego kontener jest uprzywilejowany

`privileged: true` to pierwsze, o co pyta każdy, kto czyta `docker-compose.yml`. Zostaje, bo
panel w trakcie pracy:

- tworzy przestrzeń sieciową dla każdego połączenia — `ip netns add` wymaga propagacji
  montowań na `/run/netns`, czyli `CAP_SYS_ADMIN` i braku blokady montowania przez profil
  AppArmor Dockera `docker-default`;
- tworzy pary veth, reguły NAT w iptables i polityki IPsec (XFRM) — `CAP_NET_ADMIN`;
- ustawia sysctl per interfejs (`rp_filter`, `forwarding`) dla interfejsów utworzonych przed
  chwilą, a Docker montuje `/proc/sys` tylko do odczytu, jeśli kontener nie jest
  uprzywilejowany;
- otwiera `/dev/ppp` dla pppd — w maszynie wirtualnej Docker Desktop tego urządzenia nie ma,
  więc entrypoint tworzy je przez `mknod`, na co musi pozwolić cgroup urządzeń.

Wariant z `cap_add` / `devices` / `sysctls` jest możliwy, ale nie został sprawdzony
z prawdziwym tunelem PPP, więc 3.0.0 zostaje przy `privileged`. Kontener i tak słucha tylko
na `127.0.0.0/8`: panel i przekierowane porty są dostępne wyłącznie z tego komputera.

> 📖 **Pełna instrukcja obsługi ze zrzutami ekranu:**
> [docs/MANUAL.pl.md](docs/MANUAL.pl.md) (po angielsku: [docs/MANUAL.md](docs/MANUAL.md))
> — krok po kroku, od instalacji po pierwsze połączenie RDP. Dobra na start dla każdego,
> kto nie zna się na sieciach.

## Pierwsze kroki w panelu

1. **Ustaw hasło główne** — szyfruje wszystkie zapisane profile VPN
   (AES-256-GCM). Bez niego nikt nie odczyta haseł z dysku. Nie da się go
   odzyskać, więc je zapamiętaj.
2. **Dodaj połączenie** — wypełnij formularz: typ połączenia (SSL-VPN albo IPsec),
   adres serwera VPN, login, hasło, ewentualnie zaznacz „wymaga tokena”. Niżej
   dodaj maszyny, do których chcesz się dostać (IP + port zdalny). Port lokalny
   nadaje się sam.
3. **Kliknij „Połącz”** — jeśli połączenie wymaga tokena, panel o niego zapyta.
4. **Nieznany certyfikat?** Przy pierwszym łączeniu serwer zwykle przedstawia
   certyfikat, którego panel jeszcze nie zna. Zobaczysz przycisk
   „Zaufaj certyfikatowi i połącz” — jedno kliknięcie i po sprawie. Żadnego
   ręcznego kopiowania hashy i szyfrowania plików.
5. **Gotowe** — przy każdej maszynie widzisz adres typu `127.0.0.3:13392` i menu ⋮
   z pozycjami „Połącz przez RDP”, „Kopiuj adres” i innymi. Adres możesz też wkleić
   do klienta RDP/SSH i łączyć się.

## Co warto wiedzieć

- **Kilka VPN-ów naraz** — każde połączenie działa we własnej, odizolowanej
  przestrzeni sieciowej, więc sieci różnych klientów (nawet o identycznych
  adresach IP) nie kolidują ze sobą. Typy tuneli można mieszać dowolnie.
- **IPsec** — dla dial-upu FortiGate. Trzy warianty logowania: **IKEv1 + klucz PSK
  + login/hasło (XAuth)** (najczęstszy — tak działa FortiClient), **IKEv1 na sam
  klucz PSK** i **IKEv2 na sam klucz PSK**. Adres w sieci klienta przydziela brama
  (mode config). Token (FortiToken) doklejamy do hasła — tak przyjmuje go XAuth.
  Nieobsługiwane: uwierzytelnianie certyfikatem i EAP, bo wymagałyby wgrania CA
  klienta; w takim przypadku zostaje SSL-VPN.
- **Język** — domyślnie angielski, polski do wyboru w ⚙ Ustawieniach. Wybór jedzie
  w sejfie, więc wędruje z eksportem konfiguracji; backend też się nim kieruje, dzięki
  czemu błędy połączeń i log mówią tym samym językiem, co reszta panelu.
- **Sejf** — profile leżą w `vault.enc` w folderze danych (patrz [Instalacja](#instalacja)),
  zaszyfrowane hasłem głównym. Panel i porty przekierowań są dostępne wyłącznie z tego
  komputera (nasłuch tylko na pętli zwrotnej `127.0.0.0/8`).
- **Porty lokalne** — pula `13391–13449`, przy czym **każdy port ma własny adres
  pętli zwrotnej**: `13391 → 127.0.0.2`, `13392 → 127.0.0.3`, … `13449 → 127.0.0.60`.
  Osobny adres na maszynę jest konieczny, bo Windows zapisuje poświadczenia RDP
  pod kluczem `TERMSRV/<adres>` **bez portu** — na wspólnym `localhost` hasła
  nadpisywałyby się między maszynami. Jeśli chcesz zmienić pulę, popraw oba pliki
  compose (`docker-compose.yml`, `packaging/docker-compose.yml`) **i** `app/connections.py`.
- **Aktualizacje**: panel raz na dobę pyta
  [stronę projektu](https://mysttic.github.io/Mysttic/tunnelbox/) o nowszą wersję (jej
  wydania leżą w repozytorium `Mysttic/Mysttic`, obok plików do pobrania innych programów)
  i pokazuje pasek nad listą połączeń: przy paczce ZIP na Windows przycisk „⬆️ Zaktualizuj"
  pobiera i instaluje ją bez wychodzenia z przeglądarki, przy instalacji z rejestru pasek
  pokazuje polecenie `docker compose pull`. Sprawdzanie nie wysyła żadnych Twoich danych
  i można je wyłączyć w ⚙ Ustawieniach. Szczegóły i kontrakt (tag `tunnelbox-vX.Y.Z`, plik
  `tunnelbox-X.Y.Z.zip`) w [`app/updates.py`](app/updates.py).
- **Zmiany w kodzie** — po każdej zmianie wystarczy ponownie uruchomić `./start.sh` /
  `start.bat`; przebudowuje obraz poleceniem
  `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build`.
- **Zatrzymanie panelu** — `docker compose down` w folderze z `docker-compose.yml`
  (przy paczce ZIP: w folderze programu).
- **Przesiadka z FortiVPN 2**: Tunnelbox to ten sam program pod nową nazwą, instalowany od
  nowa. FortiVPN 2 nie proponuje go jako aktualizacji, a Tunnelbox nie rusza kontenera ani
  danych FortiVPN 2. Żeby zachować połączenia, zapisz je w FortiVPN 2 przez ⚙ Ustawienia →
  „⬇️ Eksportuj konfigurację", usuń stary kontener (`docker rm -f fortivpn2-panel`, trzyma
  port 25263 i pulę portów), zainstaluj Tunnelbox i wczytaj plik przyciskiem „⬆️ Importuj"
  na jego pierwszym ekranie, podając to samo hasło główne. FortiVPN 2 już usunięty?
  Zaimportuj jego plik sejfu: `%LOCALAPPDATA%\FortiVPN2\data\vault.enc` na Windows,
  `~/.local/share/fortivpn2/data/vault.enc` na macOS i Linuksie (przy Docker Engine ten plik
  należy do roota, więc najpierw zrób kopię, którą przeczytasz:
  `sudo install -o "$USER" -m 600 ~/.local/share/fortivpn2/data/vault.enc ~/fortivpn2-vault.enc`).
  Klon ze źródeł zachowuje swój `./data`, więc tam wystarczy usunąć kontener. Gdy wszystko
  działa, usuń `%LOCALAPPDATA%\FortiVPN2` (`~/.local/share/fortivpn2`) i obrazy
  `fortivpn2-panel`.

## Architektura (dla ciekawych)

```
przeglądarka ── tunnelbox.localhost:25263 ── FastAPI (panel + API)
                                             │
                                     kontener tunnelbox
                                             │
                per połączenie: netns "vpnN" ── openfortivpn (ppp0)
                                             │   albo charon (polityki IPsec)
                                             │
 127.0.0.X:1339X ── socat ── veth ── socat ── maszyna w sieci klienta
```

- `app/main.py` — API panelu (profile, połącz/rozłącz, akceptacja certyfikatu)
- `app/vault.py` — zaszyfrowany sejf z profilami (scrypt + AES-256-GCM)
- `app/connections.py` — przestrzenie sieciowe, cykl życia tunelu, przekierowania
- `app/ipsec.py` — konfiguracja strongSwana i sterowanie demonem przez swanctl
- `app/updates.py` — codzienne sprawdzanie, czy jest nowsze wydanie
- `app/i18n.py`, `app/static/i18n.js` — katalogi tekstów po angielsku i po polsku
- `app/static/` — interfejs w przeglądarce

SSL-VPN i IPsec różnią się tylko sposobem zestawienia tunelu. openfortivpn tworzy
interfejs `ppp0` i relacjonuje postęp na stdout; IPsec nie tworzy interfejsu — ruch
kieruje polityka XFRM i osobna tablica tras (220), a stan zestawiamy i sprawdzamy
przez `swanctl`. Każdy tunel dostaje własną instancję demona `charon-systemd`,
bo polityki IPsec należą do przestrzeni sieciowej.

## Bezpieczeństwo

Panel i przekierowane porty słuchają wyłącznie na pętli zwrotnej `127.0.0.0/8`, zapisane
profile są zaszyfrowane hasłem głównym (scrypt + AES-256-GCM), a poza Twoimi tunelami VPN
panel sam łączy się tylko w jednym celu — przy codziennym sprawdzaniu aktualizacji, które
można wyłączyć. Model zagrożeń i sposób zgłaszania podatności bez zakładania publicznego
issue: [SECURITY.md](SECURITY.md) (po angielsku).

## Licencja

Własny kod Tunnelboksa jest udostępniony na [licencji MIT](LICENSE). Obraz zawiera też
openfortivpn, strongSwana, pppd, socat i inne komponenty na ich własnych licencjach; działają
jako osobne programy, a [THIRD_PARTY.md](THIRD_PARTY.md) wymienia je razem z informacją, gdzie
znaleźć ich dokładne wersje i źródła.

## Współtworzenie

Zgłoszenia błędów, pomysły i pull requesty są mile widziane —
[CONTRIBUTING.md](CONTRIBUTING.md) opisuje gałęzie (`develop` → `main`), konwencję commitów,
uruchamianie testów i odświeżanie zrzutów do instrukcji. Wydawanie nowych wersji (dla utrzymującego repo):
[docs/RELEASING.md](docs/RELEASING.md) — release buduje się automatycznie po scaleniu
`develop` → `main`. Dokumenty utrzymaniowe są po angielsku.
