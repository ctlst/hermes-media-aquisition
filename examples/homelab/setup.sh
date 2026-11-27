#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ -s gluetun/provider.tcp.ovpn ]] || { echo 'Place your provider profile at gluetun/provider.tcp.ovpn first.' >&2; exit 1; }
umask 077
mkdir -p secrets qbittorrent
for field in user password; do
    target="secrets/openvpn_$field"
    if [[ ! -s "$target" ]]; then
        read -rs -p "OpenVPN service $field: " value
        printf '\n' >&2
        [[ -n "$value" ]] || { echo 'A nonempty credential is required.' >&2; exit 1; }
        printf '%s\n' "$value" > "$target"
        unset value
    fi
done
docker compose config --quiet
docker compose up -d --wait --wait-timeout 180
echo 'Open http://127.0.0.1:18080 on the Docker host. Bind qBittorrent to tun0 and run the outage test before adding torrents.'
