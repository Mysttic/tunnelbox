#!/bin/bash
# Uruchamia panel Tunnelbox ze źródeł i otwiera go w przeglądarce (Mac/Linux).
# Obraz budowany jest lokalnie: docker-compose.build.yml nadpisuje obraz z rejestru.
set -e
cd "$(dirname "$0")"

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

echo "Starting Tunnelbox from source (the first run may take a few minutes)..."
if ! docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build; then
    echo "Could not start the panel. See the details above."
    exit 1
fi

URL="http://tunnelbox.localhost:25263"
# „open" na Linuksie bywa aliasem openvt, dlatego wybór po systemie, a nie po samej komendzie.
if [ "$(uname -s)" = "Darwin" ]; then open "$URL" || true; else xdg-open "$URL" 2>/dev/null || true; fi
echo "The panel is running at $URL"
