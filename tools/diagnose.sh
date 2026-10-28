#!/bin/sh
# Diagnostyka połączeń VPN — uruchom, gdy OBA tunele są aktywne (drugi timeoutuje):
#   docker exec tunnelbox /diagnose.sh > diag.txt
# a następnie prześlij plik diag.txt do analizy.
#
# Skrypt porównuje stan każdej przestrzeni sieciowej (netns) i sprawdza, czy z jej
# wnętrza da się dosięgnąć maszyny docelowej — to pokazuje, gdzie drugi tunel się wykłada.

echo "===================== DIAGNOSTYKA Tunnelbox ======================"
echo

echo "===== GLOBALNE ====="
echo "ip_forward:            $(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)"
echo "rp_filter all:         $(cat /proc/sys/net/ipv4/conf/all/rp_filter 2>/dev/null)"
echo "rp_filter default:     $(cat /proc/sys/net/ipv4/conf/default/rp_filter 2>/dev/null)"
echo
echo "--- iptables nat/POSTROUTING (MASQUERADE) ---"
iptables -t nat -S POSTROUTING 2>&1
echo "--- iptables filter/FORWARD (polityka) ---"
iptables -S FORWARD 2>&1 | head -3
echo
echo "--- wszystkie procesy socat ---"
ps -e -ww -o pid,args 2>/dev/null | grep -E "[s]ocat" || echo "(brak procesów socat)"
echo
echo "--- demony IPsec (charon) ---"
ps -e -ww -o pid,args 2>/dev/null | grep -E "[c]haron" || echo "(brak procesów charon)"
echo "wsparcie XFRM w jądrze: $(ip xfrm policy >/dev/null 2>&1 && echo TAK || echo NIE)"
echo

for NS in $(ip netns list 2>/dev/null | awk '{print $1}' | grep '^vpn'); do
  echo "========================================================"
  echo "===== NETNS: $NS ====="
  echo "--- adresy IP ---"
  ip netns exec "$NS" ip -o addr show 2>&1 | awk '{print "  " $2, $3, $4}'
  # SSL-VPN kończy się interfejsem ppp, IPsec nie tworzy żadnego — ruch kieruje
  # polityka XFRM. Sprawdzamy więc oba warianty, zanim uznamy tunel za martwy.
  echo "--- tunel ---"
  PPP=$(ip netns exec "$NS" ip -o link show 2>/dev/null | grep -i ppp)
  XFRM=$(ip netns exec "$NS" ip xfrm policy 2>/dev/null | grep -c "dir out")
  if [ -n "$PPP" ]; then
    echo "  SSL-VPN: $PPP"
  elif [ "${XFRM:-0}" -gt 0 ]; then
    echo "  IPsec: $XFRM polityk wychodzących"
    echo "  stan SA:"
    ip netns exec "$NS" ip -s xfrm state 2>&1 | head -12 | sed 's/^/    /'
    echo "  polityki:"
    ip netns exec "$NS" ip xfrm policy 2>&1 | grep -v "socket" | head -12 | sed 's/^/    /'
    echo "  tablica tras 220 (IPsec):"
    ip netns exec "$NS" ip route show table 220 2>&1 | sed 's/^/    /'
  else
    echo "  (BRAK tunelu — ani interfejsu ppp, ani polityk IPsec w tym netns!)"
  fi
  echo "--- tablica tras ---"
  ip netns exec "$NS" ip route 2>&1 | sed 's/^/  /'
  echo "--- rp_filter (all / veth) ---"
  echo "  all=$(ip netns exec "$NS" cat /proc/sys/net/ipv4/conf/all/rp_filter 2>/dev/null)"

  # maszyny docelowe obsługiwane w tym netns — z linii poleceń wewnętrznych socatów
  for PID in $(ip netns pids "$NS" 2>/dev/null); do
    ARGS=$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null)
    case "$ARGS" in
      *socat*TCP:*)
        REMOTE=$(printf '%s' "$ARGS" | grep -oE 'TCP:[0-9.]+:[0-9]+' | grep -v 'TCP:169\.254\.' | head -1)
        [ -z "$REMOTE" ] && continue
        IP=$(printf '%s' "$REMOTE" | cut -d: -f2)
        PORT=$(printf '%s' "$REMOTE" | cut -d: -f3)
        echo "--- maszyna docelowa $IP:$PORT ---"
        echo -n "  trasa: "
        ip netns exec "$NS" ip route get "$IP" 2>&1 | head -1
        echo -n "  test TCP: "
        ip netns exec "$NS" python3 - "$IP" "$PORT" <<'PYEOF'
import socket, sys
ip, port = sys.argv[1], int(sys.argv[2])
s = socket.socket(); s.settimeout(4)
try:
    s.connect((ip, port)); print("OSIĄGALNY (połączenie OK)")
except Exception as e:
    print("NIEOSIĄGALNY:", e)
finally:
    s.close()
PYEOF
        ;;
    esac
  done
  echo
done
echo "===================== KONIEC DIAGNOSTYKI ====================="
