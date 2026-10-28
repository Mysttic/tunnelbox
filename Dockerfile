FROM debian:bookworm-slim AS wheels
ARG TARGETARCH
# Koła Pythona osobno: na linux/arm/v7 cffi nie ma gotowego koła na PyPI i kompiluje się ze
# źródeł — kompilator zostaje w tym etapie, nie trafia do obrazu. amd64/arm64 biorą gotowe koła.
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
      $( [ "$TARGETARCH" = "arm" ] && echo "python3-dev gcc libffi-dev" ) && \
    rm -rf /var/lib/apt/lists/*
COPY app/requirements.txt /tmp/requirements.txt
RUN pip3 wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.txt

FROM debian:bookworm-slim

# policy-rc.d blokuje próby startu usług przy instalacji — w kontenerze nie ma inita,
# a postinst strongSwana bez tego wywala budowanie obrazu.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && \
    chmod +x /usr/sbin/policy-rc.d && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        openfortivpn socat iproute2 iptables ca-certificates \
        python3 python3-pip coreutils procps \
        strongswan strongswan-swanctl charon-systemd \
        libcharon-extauth-plugins \
        libstrongswan-standard-plugins libstrongswan-extra-plugins && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    rm -f /usr/sbin/policy-rc.d

# Instalacja wyłącznie z kół zbudowanych wyżej (--no-index) — ten etap nie sięga do PyPI.
# Koła są podpięte tylko na czas tego RUN (bind mount z etapu wheels): COPY + rm zostawiłby
# je w osobnej warstwie i obraz byłby większy o ich rozmiar.
COPY app/requirements.txt /app/requirements.txt
RUN --mount=type=bind,from=wheels,source=/wheels,target=/tmp/wheels \
    pip3 install --no-cache-dir --break-system-packages --no-index --find-links /tmp/wheels \
      -r /app/requirements.txt

# wersje komponentów (GPL: wskazanie wersji pakietów Debiana = dostęp do źródeł)
# set -e: brak któregoś pakietu na liście (dpkg-query kończy się błędem) przerywa budowanie.
COPY LICENSE THIRD_PARTY.md /usr/share/doc/tunnelbox/
RUN set -e; { echo "# Debian packages (binary, version, source)"; \
      dpkg-query -W -f='${binary:Package}\t${Version}\t${source:Package}\n' \
        openfortivpn ppp strongswan-charon strongswan-swanctl charon-systemd socat iproute2 iptables \
        python3 libstrongswan libstrongswan-standard-plugins libstrongswan-extra-plugins libcharon-extauth-plugins; \
      echo; echo "# Python packages"; pip3 freeze --all 2>/dev/null; } \
    > /usr/share/doc/tunnelbox/third-party-versions.txt

COPY app /app
COPY VERSION /app/VERSION
COPY entrypoint.sh /entrypoint.sh
COPY tools/diagnose.sh /diagnose.sh
RUN chmod +x /entrypoint.sh /diagnose.sh
WORKDIR /app

# Opis obrazu (OCI) — CI dokłada własne etykiety, te tutaj opisują też obraz z paczki ZIP
# i zbudowany lokalnie ze źródeł.
LABEL org.opencontainers.image.title="Tunnelbox" \
      org.opencontainers.image.source="https://github.com/Mysttic/tunnelbox" \
      org.opencontainers.image.licenses="MIT"

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
