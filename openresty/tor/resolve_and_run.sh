#!/bin/sh
set -eu
RESOLVE_TRIES=120
SLEEP_SEC=2
IP="${OPENRESTY_IP:-}"
if [ -z "${IP}" ]; then
  i=0
  while [ $i -lt $RESOLVE_TRIES ]; do
    for H in openresty_antiddos openresty; do
      CANDIDATE="$(getent hosts "$H" | awk '{print $1}' | tail -n1 || true)"
      if [ -n "${CANDIDATE}" ]; then
        IP="${CANDIDATE}"
        break
      fi
    done
    if [ -n "${IP}" ]; then
      break
    fi
    i=$((i+1))
    sleep "${SLEEP_SEC}"
  done
fi
if [ -z "${IP}" ]; then
  echo "Failed to resolve openresty host after $((RESOLVE_TRIES*SLEEP_SEC)) seconds" >&2
  exit 1
fi
echo "Resolved OpenResty IP: ${IP}" >&2
cat >/tmp/torrc <<EOF
SocksPort 0.0.0.0:9050
DataDirectory /var/lib/tor
HiddenServiceDir /var/lib/tor/hidden_service/
HiddenServicePort 80 ${IP}:80
Log notice stdout
RunAsDaemon 0
ControlPort 9051
EOF
exec /usr/local/bin/tor -f /tmp/torrc
