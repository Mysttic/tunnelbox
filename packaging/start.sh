#!/bin/bash
# Uruchamia panel Tunnelbox z obrazu dołączonego do paczki (Mac/Linux).
#
# Aktualizacja działa sama: skrypt przenosi zapisane połączenia z poprzedniej wersji,
# usuwa stary kontener i stare obrazy, po czym uruchamia nową wersję.
set -e
# sejf (także jego kopia robocza) to dane tylko dla użytkownika — inni użytkownicy tego
# komputera nie mają czego czytać w katalogu danych ani w kopii w katalogu tymczasowym
umask 077
cd "$(dirname "$0")"

CONTAINER=tunnelbox
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/tunnelbox/data"
# Katalog roboczy na czas instalacji — tworzony dopiero przy pierwszej kopii (mktemp: własny,
# z prawami 0700, więc nikt nie podłoży go wcześniej) i kasowany po potwierdzeniu importu.
STAGING_DIR=""

# Pula przekierowań nasłuchuje na 127.0.0.2…127.0.0.60 (każda maszyna ma własny adres).
# Linux kieruje całe 127.0.0.0/8 na pętlę zwrotną sam, ale macOS ma na lo0 tylko
# 127.0.0.1 — bez aliasów Docker Desktop nie zbinduje pozostałych adresów i kontener
# nie wystartuje. Aliasy znikają po restarcie komputera, stąd sprawdzenie przy każdym starcie.
ensure_loopback_aliases() {
    [ "$(uname -s)" = "Darwin" ] || return 0
    missing=""
    for i in $(seq 2 60); do
        ifconfig lo0 | grep -q "inet 127.0.0.$i " || missing="$missing $i"
    done
    [ -n "$missing" ] || return 0

    echo "macOS: the port-forwarding pool listens on 127.0.0.2-127.0.0.60, and Docker Desktop"
    echo "for Mac cannot bind these addresses until they are added as aliases of lo0."
    echo "Adding them now (sudo will ask for your password once)."
    echo "The aliases disappear after a reboot — just run ./start.sh again then."
    for i in $missing; do
        if ! sudo ifconfig lo0 alias "127.0.0.$i" up; then
            echo "Could not add the loopback alias 127.0.0.$i. Run ./start.sh again and enter your password."
            exit 1
        fi
    done
}

# Ścieżka katalogu podpiętego jako /data w danym kontenerze (pusta, gdy go nie ma).
container_data_path() {
    docker inspect --type container "$1" \
        --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' 2>/dev/null || true
}

# Usuwa stare obrazy programu z repozytorium $1 poza obrazem $2 — tylko tagi wyglądające
# jak wersja (X.Y.Z), więc nie ruszamy np. lokalnego :latest/:dev ani innych repozytoriów.
# Pętla zamiast „xargs -r", którego nie zna xargs z macOS.
remove_version_tags() {
    docker images "$1" --format '{{.Repository}}:{{.Tag}}' 2>/dev/null \
        | grep -v '<none>' | grep -vFx "${2:-<none>}" | grep -E ':[0-9]+\.[0-9]+\.[0-9]+$' \
        | while read -r tag; do docker rmi "$tag" >/dev/null 2>&1 || true; done
}

# Sejf zapisuje panel z wnętrza kontenera. Na Linuksie z Docker Engine plik należy wtedy
# do roota i ma prawa 0600, więc zwykłe cp/cmp użytkownika dostają „Permission denied".
# W takim wypadku sięgamy do pliku przez Dockera — obrazem z tej paczki (wczytanym niżej),
# tak samo jak robi to sam panel. Docker Desktop (macOS) mapuje właściciela na użytkownika,
# więc tam wystarcza zwykła kopia. label=disable: przy SELinuksie (np. Fedora) zwykły
# kontener nie dostałby się do pliku w katalogu domowym — panel też działa bez etykiet.
abs_dir() { (cd "$1" && pwd); }
docker_vault() { docker run --rm --security-opt label=disable "$@"; }
read_vault() {      # $1 = katalog z vault.enc, $2 = plik docelowy
    if [ -r "$1/vault.enc" ]; then cp "$1/vault.enc" "$2"; return; fi
    docker_vault --entrypoint cat -v "$(abs_dir "$1"):/src:ro" "$DESIRED" /src/vault.enc > "$2"
}
same_vault() {      # $1 = kopia robocza, $2 = katalog z vault.enc
    if [ -r "$2/vault.enc" ]; then cmp -s "$1" "$2/vault.enc"; return; fi
    docker_vault --entrypoint cat -v "$(abs_dir "$2"):/src:ro" "$DESIRED" /src/vault.enc | cmp -s "$1" -
}
write_vault() {     # $1 = kopia robocza, $2 = katalog docelowy
    if [ -w "$2" ] && { [ ! -e "$2/vault.enc" ] || [ -w "$2/vault.enc" ]; }; then
        cp "$1" "$2/vault.enc"; return
    fi
    docker_vault --entrypoint cp -v "$(abs_dir "$(dirname "$1")"):/src:ro" \
        -v "$(abs_dir "$2"):/dst" "$DESIRED" "/src/$(basename "$1")" /dst/vault.enc
}

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Install Docker Desktop or Docker Engine: https://docs.docker.com/get-docker/"
    exit 1
fi
# oba strumienie: Docker 20.10 pisze błąd uprawnień na stdout, nowsze wersje na stderr
if ! docker_err="$(docker info 2>&1)"; then
    case "$docker_err" in
        *"permission denied"*)
            echo "Docker is running, but your user cannot use it. Add yourself to the docker group"
            echo "(sudo usermod -aG docker \"\$USER\"), log out and back in, then run ./start.sh again." ;;
        *)
            echo "Docker is not running. Start Docker Desktop or Docker Engine and try again." ;;
    esac
    exit 1
fi

ensure_loopback_aliases

# --- dane użytkownika (poza folderem programu) + migracja z poprzedniej wersji ---
mkdir -p "$DATA_DIR"
export TUNNELBOX_DATA="$DATA_DIR"

# --- wczytanie nowego obrazu ---
TAR="$(ls tunnelbox-image-*.tar.gz 2>/dev/null | head -1)"
if [ -z "$TAR" ]; then
    echo "Image file not found (tunnelbox-image-*.tar.gz). Extract the whole ZIP package."
    exit 1
fi

echo "Loading the Tunnelbox image into Docker (the first run takes a moment)..."
if ! docker load -i "$TAR"; then
    echo "Could not load the image from $TAR. Check that the file is not damaged."
    exit 1
fi

DESIRED="$(grep -oE '^[[:space:]]*image:[[:space:]]*[^[:space:]]+' docker-compose.yml | head -1 | awk '{print $2}')"

# KROK 1 — kopia robocza istniejącej konfiguracji, zanim cokolwiek ruszymy (wczytanie
# obrazu danych nie dotyka, a obraz bywa potrzebny do odczytu sejfu — patrz read_vault).
# Kandydaci: bieżąca konfiguracja, kontener poprzedniej wersji (może już nie istnieć po
# „docker compose down"), ten sam folder, folder nadrzędny i sąsiednie paczki: ZIP
# rozpakowuje się do katalogu z numerem wersji, więc stara wersja stoi zwykle obok.
PREV="$(container_data_path "$CONTAINER")"
STAGED=""
for candidate in "$DATA_DIR" "$PREV" "./data" "../data" ../*/data; do
    [ -n "$candidate" ] || continue
    [ -f "$candidate/vault.enc" ] || continue
    STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tunnelbox-migration.XXXXXX")"
    if ! read_vault "$candidate" "$STAGING_DIR/vault.enc"; then
        echo "Could not read $candidate/vault.enc — nothing was changed."
        echo "Make it readable for your user (sudo chown \"$(id -un)\" \"$candidate/vault.enc\")"
        echo "and run ./start.sh again."
        rm -rf "$STAGING_DIR"
        exit 1
    fi
    STAGED="$STAGING_DIR/vault.enc"
    echo "Backed up the current configuration for the duration of the install (source: $candidate)."
    break
done

# --- usunięcie poprzedniej wersji (tylko gdy to faktycznie aktualizacja) ---
CURRENT="$(docker inspect --type container "$CONTAINER" --format '{{.Config.Image}}' 2>/dev/null || true)"
FOLDER="$(docker inspect --type container "$CONTAINER" \
    --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' 2>/dev/null || true)"
if [ -n "$CURRENT" ] && [ -n "$DESIRED" ] && [ "$CURRENT" != "$DESIRED" ]; then
    echo "Previous version detected ($CURRENT) — removing it..."
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    remove_version_tags tunnelbox "$DESIRED"
elif [ -n "$CURRENT" ] && [ "$FOLDER" != "$PWD" ]; then
    # Ta sama wersja, ale uruchomiona z innego folderu (paczka rozpakowana drugi raz).
    # Compose nie przejmie kontenera z innego folderu — zgłosiłby konflikt nazwy,
    # więc tworzymy go od nowa stąd (tak samo jak start.ps1).
    echo "The panel was started from another folder — recreating it from this one..."
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
fi

if ! docker compose up -d; then
    echo "Could not start the panel. See the details above."
    [ -z "$STAGED" ] || echo "The backup copy of your configuration is waiting in: $STAGED"
    exit 1
fi

URL="http://tunnelbox.localhost:25263"          # adres dla przeglądarki (nazwa)
API="http://127.0.0.1:25263"         # adres dla skryptu (IP — pewny w każdym narzędziu)

# KROK 2 — wczytanie konfiguracji do nowej wersji i potwierdzenie.
panel_status() {
    curl -s --max-time 3 "$API/api/vault" 2>/dev/null || true
}
wait_for_panel() {
    for _ in $(seq 1 "${1:-60}"); do
        out="$(panel_status)"
        if [ -n "$out" ]; then echo "$out"; return 0; fi
        sleep 1
    done
    return 1
}

if [ -n "$STAGED" ]; then
    if STATUS="$(wait_for_panel 60)"; then
        case "$STATUS" in
            *'"exists":true'*) ;;
            *)
                if ! write_vault "$STAGED" "$DATA_DIR"; then
                    echo "Could not write $DATA_DIR/vault.enc."
                    echo "The backup copy is waiting in: $STAGED"
                    exit 1
                fi
                STATUS="$(wait_for_panel 20 || true)" ;;
        esac
        if [ -n "$STATUS" ] && [ "${STATUS#*\"exists\":true}" != "$STATUS" ] \
           && same_vault "$STAGED" "$DATA_DIR"; then
            echo "Configuration moved to the new version and confirmed."
            rm -rf "$STAGING_DIR"
        else
            echo "Could not confirm that the configuration was moved."
            echo "The backup copy is waiting in: $STAGED"
            echo "To restore it: stop the panel and copy this file to $DATA_DIR"
        fi
    else
        echo "The panel did not respond — cannot confirm that the configuration was moved."
        echo "The backup copy is waiting in: $STAGED"
    fi
fi

# „open" na Linuksie bywa aliasem openvt, dlatego wybór po systemie, a nie po samej komendzie.
if [ "$(uname -s)" = "Darwin" ]; then open "$URL" || true; else xdg-open "$URL" 2>/dev/null || true; fi
echo "The panel is running at $URL"
echo "Your connections are stored in: $DATA_DIR"
