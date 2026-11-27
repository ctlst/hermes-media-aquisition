#!/usr/bin/env bash
# First-run IPv4 test, from the Linux Docker host, with an empty queue.
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ "${1:-}" == --empty-queue ]] || { echo 'Confirm a new empty queue, then run with --empty-queue.' >&2; exit 2; }
vpn=$(docker compose ps -q gluetun)
qb=$(docker compose ps -q qbittorrent)
[[ -n "$vpn" && -n "$qb" ]]
[[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$qb")" == "container:$vpn" ]]
docker exec "$qb" sh -ec 'test ! -e /proc/sys/net/ipv6/conf/all/disable_ipv6 || test "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" = 1'
pid=$(docker inspect -f '{{.State.Pid}}' "$vpn")
[[ "$pid" =~ ^[0-9]+$ && "$pid" -gt 1 ]]
sudo -v
link=(sudo nsenter -t "$pid" -n ip link)
"${link[@]}" show tun0 >/dev/null
dest=$(getent ahostsv4 api.ipify.org | awk 'NR==1 {print $1}')
[[ -n "$dest" ]]
probe() {
    docker exec "$qb" curl -4fsS --noproxy '*' --connect-timeout 4 --max-time 8 \
        --resolve "api.ipify.org:443:$dest" "$@" https://api.ipify.org
}
baseline=$(probe)
[[ -n "$baseline" ]] || { echo 'Could not establish VPN egress.' >&2; exit 1; }
blocked() {
    local rc=0
    probe "$@" >/dev/null || rc=$?
    case "$rc" in
        7|28) return 0 ;;
        *) echo "Expected a blocked connection; curl returned $rc." >&2; return 1 ;;
    esac
}
blocked --interface eth0
recover() {
    docker unpause "$vpn" >/dev/null && docker compose up -d --force-recreate --wait --wait-timeout 180
}
docker pause "$vpn" >/dev/null
trap 'recover' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${link[@]}" set tun0 down
blocked
blocked --interface eth0
trap - EXIT INT TERM
recover
qb=$(docker compose ps -q qbittorrent)
vpn=$(docker compose ps -q gluetun)
[[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$qb")" == "container:$vpn" ]]
probe >/dev/null
echo 'IPv4 egress worked before and after the outage. Default and direct-interface probes were blocked with tun0 down.'
