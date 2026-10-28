#!/bin/sh
set -e

# /dev/ppp bywa nieobecny w VM Docker Desktop (zwłaszcza na Macu). Przy privileged
# możemy go utworzyć ręcznie — openfortivpn i tak zweryfikuje wsparcie PPP w jądrze.
if [ ! -c /dev/ppp ]; then
    mknod /dev/ppp c 108 0 2>/dev/null || true
fi

exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
