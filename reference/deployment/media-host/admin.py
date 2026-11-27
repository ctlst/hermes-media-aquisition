#!/usr/bin/env python3
"""Local media-host setup. No admin actions are exposed through the Hermes SSH key."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import urllib.request
from media_backend import ROOT, DOWNLOADS, QB, containers, fingerprint, guard


def secret_file(name, value):
    p = ROOT / 'secrets' / name
    p.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(value + '\n')
    p.chmod(0o600)


def preflight():
    for path, dataset in [(DOWNLOADS, 'tank/media'), (Path('/srv/appdata/agent-media'), 'tank/appdata')]:
        result = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE,FSTYPE', '-T', str(path)], text=True).split()
        if result != [dataset, 'zfs'] or not path.is_dir():
            raise RuntimeError('Expected ZFS dataset is not mounted: ' + str(path))
    for n in ('openvpn_user', 'openvpn_password'):
        p = ROOT / 'secrets' / n
        if not p.exists() or not p.read_text().strip():
            raise RuntimeError('NordVPN service credentials missing; run admin.py credentials on media-host')
    subprocess.run(['docker', 'compose', 'config', '--quiet'], cwd=ROOT, check=True)


def bootstrap():
    preflight()
    subprocess.run(['docker', 'compose', 'up', '-d', '--wait', '--wait-timeout', '180'], cwd=ROOT, check=True)
    path = ROOT / 'secrets/qbittorrent.json'
    if path.exists():
        q = QB()
    else:
        # Read the generated password into process memory, never terminal output.
        for _ in range(30):
            logs = subprocess.check_output(['docker', 'logs', 'agent-qbittorrent'], stderr=subprocess.STDOUT, text=True)
            found = re.findall(r'temporary password is provided for this session: (\S+)', logs)
            if found:
                break
            time.sleep(1)
        if not found:
            raise RuntimeError('No initial qBittorrent password found; inspect setup privately')
        q = QB(password=found[-1])
        password = secrets.token_urlsafe(32)
        # Save before mutation so a later failure doesn't lose the intended password.
        secret_file('qbittorrent.json', json.dumps({'username': 'admin', 'password': password}))
        q.call('app/setPreferences', {'json': json.dumps({'web_ui_password': password})})
        q = QB()
    q.call('app/setPreferences', {'json': json.dumps({
        'current_network_interface': 'tun0', 'save_path': '/downloads/complete',
        'temp_path_enabled': True, 'temp_path': '/downloads/incomplete',
        'upnp': False, 'bypass_local_auth': False, 'bypass_auth_subnet_whitelist_enabled': False,
        'web_ui_csrf_protection_enabled': True, 'web_ui_host_header_validation_enabled': True,
        'autorun_enabled': False, 'auto_delete_mode': 0, 'max_active_downloads': 3,
    })})
    guard(q, require_acceptance=False)
    print('qBittorrent configured and authenticated. VPN acceptance still required before adding torrents.')


def probe(interface=None):
    cmd = ['docker', 'exec', 'agent-qbittorrent', 'curl', '-4', '--silent', '--show-error',
           '--fail', '--connect-timeout', '5', '--max-time', '10']
    if interface:
        cmd += ['--interface', interface]
    cmd += ['https://api.ipify.org']
    return subprocess.run(cmd, text=True, capture_output=True, timeout=15)


def verify():
    service = subprocess.run(['systemctl', 'is-active', '--quiet', 'agent-media'], capture_output=True)
    if service.returncode == 0:
        raise RuntimeError('Stop agent-media.service, then run bootstrap and verify manually; otherwise systemd would restart containers during the outage test')
    q = QB()
    guard(q, require_acceptance=False)
    if q.json('torrents/info'):
        raise RuntimeError('Initial acceptance test requires an empty torrent queue')
    accepted = ROOT / 'vpn-accepted.json'
    accepted.unlink(missing_ok=True)
    baseline = probe()
    if baseline.returncode or not baseline.stdout.strip():
        raise RuntimeError('Cannot establish VPN egress baseline')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('https://api.ipify.org', timeout=15) as r:
        host_ip = r.read().decode().strip()
    if baseline.stdout.strip() == host_ip:
        raise RuntimeError('VPN egress equals host egress; investigate before acceptance')
    # Force a numeric destination on eth0 so DNS failure cannot mask an IP leak.
    import socket
    address = socket.getaddrinfo('api.ipify.org', 443, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    pinned = subprocess.run(['docker', 'exec', 'agent-qbittorrent', 'curl', '-4', '--silent', '--fail',
                             '--resolve', 'api.ipify.org:443:' + address,
                             '--connect-timeout', '5', '--max-time', '10', 'https://api.ipify.org'],
                            capture_output=True, text=True, timeout=15)
    if pinned.returncode or pinned.stdout.strip() != baseline.stdout.strip():
        raise RuntimeError('Numeric test endpoint is not reachable through the VPN baseline')
    def blocked_probe():
        cmd = ['docker', 'exec', 'agent-qbittorrent', 'curl', '-4', '--silent', '--fail',
               '--interface', 'eth0', '--resolve', 'api.ipify.org:443:' + address,
               '--connect-timeout', '5', '--max-time', '10', 'https://api.ipify.org']
        return subprocess.run(cmd, capture_output=True, timeout=15).returncode
    if blocked_probe() not in (7, 28):
        raise RuntimeError('Direct-interface probe did not demonstrate a blocked route')
    # Freeze the VPN cgroup, including its recovery supervisor. Sending SIGSTOP
    # to namespace PID 1 from inside that namespace can be ignored by Linux.
    # The separate qBittorrent cgroup stays running in the shared network.
    host_pid = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Pid}}', 'agent-gluetun'], text=True).strip()
    if not host_pid.isdigit() or int(host_pid) <= 1:
        raise RuntimeError('Expected a running Gluetun host PID')
    netcmd = ['sudo', '-n', 'nsenter', '-t', host_pid, '-n', 'ip']
    try:
        subprocess.run(['docker', 'pause', 'agent-gluetun'], check=True, capture_output=True)
        subprocess.run(netcmd + ['link', 'set', 'tun0', 'down'], check=True, capture_output=True)
        if blocked_probe() not in (7, 28):
            raise RuntimeError('Direct egress was not blocked during tunnel failure')
        result = subprocess.run(['docker', 'exec', 'agent-qbittorrent', 'curl', '-4', '--silent', '--fail',
                                 '--resolve', 'api.ipify.org:443:' + address,
                                 '--connect-timeout', '5', '--max-time', '10', 'https://api.ipify.org'], capture_output=True, timeout=15)
        if result.returncode not in (7, 28):
            raise RuntimeError('Default egress was not demonstrably blocked during tunnel failure (curl exit ' + str(result.returncode) + ')')
        state = subprocess.check_output(netcmd + ['-j', 'link', 'show', 'tun0'], text=True)
        if 'UP' in json.loads(state)[0]['flags']:
            raise RuntimeError('Tunnel recovered during test; repeat under controlled conditions')
    finally:
        subprocess.run(['docker', 'unpause', 'agent-gluetun'], capture_output=True)
        subprocess.run(['docker', 'compose', 'down'], cwd=ROOT, check=True, capture_output=True)
        subprocess.run(['docker', 'compose', 'up', '-d', '--wait', '--wait-timeout', '180'], cwd=ROOT, check=True, capture_output=True)
    guard(QB(), require_acceptance=False)
    if probe().returncode:
        raise RuntimeError('VPN did not recover after the failure test')
    accepted.write_text(json.dumps({'fingerprint': fingerprint(containers()), 'tested_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                    'tests': ['different-egress', 'eth0-blocked', 'tunnel-down-blocked', 'recovery']}) + '\n')
    print('VPN egress, direct-route blocking, tunnel failure, and recovery verified.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['credentials', 'preflight', 'bootstrap', 'verify'])
    a = p.parse_args()
    os.chdir(ROOT)
    if a.action == 'credentials':
        username = getpass.getpass('NordVPN service username (hidden): ').strip()
        if '@' in username:
            raise SystemExit('Use the username from Nord Account > NordVPN > Manual setup > Service credentials, not your email or Google login. Saved files were not changed.')
        password = getpass.getpass('NordVPN service password (hidden): ').strip()
        if not username or not password:
            raise SystemExit('Both service credentials are required')
        secret_file('openvpn_user', username)
        secret_file('openvpn_password', password)
        print('Saved private service credential files.')
    elif a.action == 'preflight':
        preflight()
    elif a.action == 'bootstrap':
        bootstrap()
    else:
        verify()
