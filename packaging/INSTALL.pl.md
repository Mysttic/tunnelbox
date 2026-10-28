# Tunnelbox — instalacja

*[🇬🇧 English](README.md) · 🇵🇱 Polski*

Panel do łączenia z VPN-ami Fortinet (SSL-VPN i IPsec), obsługiwany w całości przez
przeglądarkę. Tunnelbox, dawniej FortiVPN 2 (tak nazywał się do wersji 2.9), nie jest
powiązany z firmą Fortinet ani przez nią popierany.

## Uruchomienie (3 kroki)

1. Zainstaluj i uruchom **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**
   (na Linuksie wystarczy Docker Engine).
2. Kliknij dwukrotnie **`start.bat`** (Windows) lub uruchom `./start.sh` (Mac/Linux).
   Skrypt wczytuje dołączony obraz (`tunnelbox-image-X.Y.Z.tar.gz`) do Dockera
   (`docker load`) i uruchamia panel — nic nie budujesz i nic nie pobierasz z internetu.
   Na Macu raz poprosi o hasło, żeby dodać lokalne adresy potrzebne panelowi (znikają po
   restarcie komputera — wtedy po prostu uruchom `./start.sh` ponownie).
3. Panel otworzy się sam pod adresem **http://tunnelbox.localhost:25263**.

Panel działa w tle — nie trzeba trzymać otwartego terminala.

## Język

Panel startuje po angielsku. Aby przełączyć na polski: **⚙ Settings → Language →
Polski**. Wybór obejmuje cały interfejs, łącznie z komunikatami połączeń, i zapisuje
się razem z konfiguracją.

## Szybkie łączenie RDP

Działa od razu — `start.bat` konfiguruje to sam. Kliknięcie „Połącz przez RDP"
w panelu otwiera pulpit zdalny wprost adresem maszyny — bez zapisywania pliku `.rdp`,
więc Windows nie pokazuje ostrzeżenia o „nieznanym wydawcy" przy każdym połączeniu,
a schowek działa od razu. Przy pierwszym użyciu przeglądarka poprosi o zgodę na
otwarcie aplikacji — zaznacz „Zawsze zezwalaj".

Nie chcesz tej funkcji? W panelu: **⚙ Ustawienia → Szybkie łączenie RDP** — wtedy
przycisk zmieni się na „Pobierz plik .rdp".

## Pełna instrukcja

Szczegółowy przewodnik krok po kroku, ze zrzutami ekranu, znajdziesz w pliku
**[docs/MANUAL.pl.md](docs/MANUAL.pl.md)** w tej paczce (po angielsku:
**[docs/MANUAL.md](docs/MANUAL.md)**).

## Aktualizacja

Panel sam pilnuje wersji. Gdy pojawi się nowsza, nad listą połączeń wyświetla pasek
z przyciskiem **„⬆️ Zaktualizuj"** — kliknięcie pobiera paczkę i instaluje ją w tle
(postęp widać w osobnym oknie). Nic nie trzeba rozpakowywać.

Można też jak dotąd: pobrać paczkę ze
[strony projektu](https://mysttic.github.io/Mysttic/tunnelbox/), rozpakować
**gdziekolwiek** i uruchomić `start.bat`. Reszta dzieje się sama — skrypt przenosi zapisane
połączenia z poprzedniej wersji, usuwa jej kontener i obraz, po czym uruchamia nową.

Sprawdzanie aktualizacji można wyłączyć: **⚙ Ustawienia → Sprawdzaj aktualizacje**.
Panel nie wysyła przy nim żadnych Twoich danych — pyta tylko o listę wydań.

Twoje połączenia (`vault.enc`) leżą poza folderem programu, w
`%LOCALAPPDATA%\Tunnelbox\data` (Mac/Linux: `~/.local/share/tunnelbox/data`), więc nie
zależą od tego, gdzie rozpakujesz paczkę. Hasło główne i ustawienia panelu pozostają bez
zmian.

## Przesiadka z FortiVPN 2

Tunnelbox to FortiVPN 2 pod nową nazwą, ale instaluje się od nowa: FortiVPN 2 się do niego
nie aktualizuje, a ta paczka nie rusza kontenera ani danych FortiVPN 2. Żeby przenieść
zapisane połączenia:

1. W FortiVPN 2: **⚙ Ustawienia → „⬇️ Eksportuj konfigurację"**. Dostaniesz plik `.enc`
   zaszyfrowany Twoim hasłem głównym.
2. Usuń kontener FortiVPN 2, który zajmuje port panelu: `docker rm -f fortivpn2-panel`
   (albo usuń go w Docker Desktop → Containers).
3. Zainstaluj Tunnelbox tak, jak opisano wyżej.
4. Na pierwszym ekranie Tunnelboksa kliknij **„⬆️ Importuj"**, wybierz wyeksportowany plik
   i wpisz to samo hasło główne.

FortiVPN 2 już usunięty? Zaimportuj jego plik sejfu:
`%LOCALAPPDATA%\FortiVPN2\data\vault.enc` (Mac/Linux:
`~/.local/share/fortivpn2/data/vault.enc`; na Linuksie z Docker Engine ten plik należy do
roota, więc najpierw skopiuj go przez `sudo`). Gdy wszystko działa, usuń folder
`%LOCALAPPDATA%\FortiVPN2` (Mac/Linux: `~/.local/share/fortivpn2`) i obrazy
`fortivpn2-panel` w Docker Desktop → Images. Zmienia się też zakładka: panel otwiera się
teraz pod adresem **http://tunnelbox.localhost:25263**.

## Zatrzymanie

W folderze programu uruchom `docker compose down`.

## Coś nie działa?

Skrypt startowy pisze komunikaty po angielsku:

- **„Image file … not found"** (nie znaleziono pliku obrazu) — rozpakuj **całą** paczkę ZIP
  (plik `tunnelbox-image-*.tar.gz` musi leżeć obok `start.bat`).
- **„Docker not found"** (nie znaleziono Dockera) — najpierw zainstaluj Docker Desktop (na
  Linuksie Docker Engine).
- **„Docker is not running"** (Docker nie działa) — uruchom Docker Desktop i poczekaj, aż
  w pełni wstanie.
- **„Could not add the loopback alias …"** (Mac; nie udało się dodać aliasu pętli zwrotnej)
  — uruchom `./start.sh` ponownie i podaj hasło, gdy `sudo` o nie zapyta.
