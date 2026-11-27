#!/usr/bin/env python3
"""Fixed media operations for the dedicated Hermes SSH key."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DOWNLOADS = Path('/srv/media/downloads/agent')
VIDEO = Path('/srv/media/library')
MEDIA = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.ts', '.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx'}


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=25)
    if r.returncode:
        raise RuntimeError('Host command failed; check container/service status on media-host')
    return r.stdout


def request(url, data=None, headers=None, opener=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data is not None else None,
                                 headers=headers or {})
    op = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(req, timeout=20) as response:
        return response.read()


def plex(path):
    token = (ROOT / 'secrets/plex_token').read_text().strip()
    return request('http://127.0.0.1:32400' + path, headers={'X-Plex-Token': token})


def libraries():
    root = ET.fromstring(plex('/library/sections'))
    return [dict(id=int(d.get('key')), title=d.get('title'), type=d.get('type'),
                 paths=[x.get('path') for x in d.findall('Location')]) for d in root.findall('Directory')]


def section(value):
    for s in libraries():
        if s['id'] == int(value):
            return s
    raise ValueError('Unknown Plex section')


class QB:
    def __init__(self, password=None):
        if password is None and not (ROOT / 'secrets/qbittorrent.json').exists():
            raise RuntimeError('Torrent service is not initialized; finish NordVPN setup and run admin.py bootstrap on media-host')
        creds = json.loads((ROOT / 'secrets/qbittorrent.json').read_text()) if password is None else {'username': 'admin', 'password': password}
        cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                  urllib.request.HTTPCookieProcessor(cookies))
        # qBittorrent 5.2 returns HTTP 204 with an empty body; earlier versions
        # return "Ok.". The new cookie name also includes the WebUI port.
        if self.call('auth/login', creds).strip() not in (b'Ok.', b'') or not any(c.name in ('SID', 'QBT_SID_18080') for c in cookies):
            raise RuntimeError('qBittorrent authentication failed')

    def call(self, path, data=None):
        return request('http://127.0.0.1:18080/api/v2/' + path, data,
                       {'Referer': 'http://127.0.0.1:18080/'}, self.opener)

    def json(self, path):
        return json.loads(self.call(path))


def containers():
    r = subprocess.run(['docker', 'inspect', 'agent-gluetun', 'agent-qbittorrent'],
                       text=True, capture_output=True, timeout=15)
    return json.loads(r.stdout or '[]')


def fingerprint(cs):
    # Container IDs change across ordinary down/up; guard separately verifies
    # that the running torrent container shares the current Gluetun namespace.
    payload = sorted((c['Name'], c['Image']) for c in cs)
    return hashlib.sha256((json.dumps(payload, sort_keys=True) + (ROOT / 'compose.yml').read_text()).encode()).hexdigest()


def guard(q, require_acceptance=True):
    cs = containers()
    byname = {c['Name'].lstrip('/'): c for c in cs}
    vpn = byname.get('agent-gluetun', {})
    qb = byname.get('agent-qbittorrent', {})
    if vpn.get('State', {}).get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('VPN is not healthy; do not start downloads')
    if not qb.get('State', {}).get('Running') or qb['HostConfig']['NetworkMode'] != 'container:' + vpn['Id']:
        raise RuntimeError('qBittorrent must share the current Gluetun network namespace')
    if q.json('app/preferences').get('current_network_interface') != 'tun0':
        raise RuntimeError('qBittorrent is not bound to tun0')
    if require_acceptance:
        p = ROOT / 'vpn-accepted.json'
        if not p.exists() or json.loads(p.read_text()).get('fingerprint') != fingerprint(cs):
            raise RuntimeError('VPN acceptance missing or stack changed; run the operations runbook')


def torrent_hash(a):
    h = a.get('hash') or ''
    if not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', h):
        raise ValueError('Provide one torrent hash')
    return h.lower()


def safe_relative(value):
    p = PurePosixPath(value)
    if p.is_absolute() or not p.parts or any(x in ('..', '.') for x in p.parts) or '\\' in value or '\x00' in value:
        raise ValueError('Expected a relative path without traversal')
    return p


def checked_path(root, relative):
    p = root / safe_relative(relative)
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes its media root')
    current = p
    while current != root:
        if current.is_symlink():
            raise ValueError('Symlinks are not allowed for imports')
        current = current.parent
    return p


def import_file(q, a):
    h = torrent_hash(a)
    info = q.json('torrents/info?hashes=' + h)
    if len(info) != 1 or info[0]['amount_left'] != 0 or info[0]['progress'] < 1 or 'checking' in info[0]['state'].lower():
        raise ValueError('Torrent must be fully downloaded and not checking')
    files = q.json('torrents/files?hash=' + h)
    selected = [f for f in files if f['index'] == a.get('file_index')]
    if len(selected) != 1 or selected[0]['progress'] < 1:
        raise ValueError('Selected file is not complete')
    save = PurePosixPath(info[0]['save_path'])
    if not save.is_relative_to('/downloads'):
        raise ValueError('Torrent is outside the managed downloads')
    relative = str(save.relative_to('/downloads') / safe_relative(selected[0]['name']))
    source = checked_path(DOWNLOADS, relative)
    if not source.is_file() or source.suffix.lower() not in MEDIA or source.stat().st_size != selected[0]['size']:
        raise ValueError('Expected a complete media file of the recorded size')
    s = section(a['section'])
    library = None
    for path in s['paths']:
        library_path = PurePosixPath(path)
        if library_path.is_relative_to('/data/VIDEO'):
            candidate = checked_path(VIDEO, str(library_path.relative_to('/data/VIDEO')))
            if candidate.is_dir():
                library = candidate
                break
    if library is None:
        raise ValueError('No existing recognized Plex media root; check storage before importing')
    dest = checked_path(library, a['destination'])
    if dest.suffix.lower() != source.suffix.lower():
        raise ValueError('Keep the original media extension')
    if dest.exists():
        if os.path.samefile(source, dest):
            return {'already_imported': str(dest), 'section': s['id']}
        raise ValueError('Destination exists; refusing to overwrite')
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, dest, follow_symlinks=False)
    return {'imported': str(dest), 'section': s['id'], 'scan_requested': False}


def main(a):
    action = a['action']
    if action not in {'status', 'libraries', 'search', 'scan', 'torrents', 'files', 'add', 'start', 'stop', 'import'}:
        raise ValueError('Unsupported media operation')
    if action == 'status':
        cs = containers()
        return {'containers': [{'name': c['Name'], 'state': c['State']['Status'], 'health': c['State'].get('Health', {}).get('Status')} for c in cs],
                'nord_credentials_present': all((ROOT / 'secrets' / n).exists() and (ROOT / 'secrets' / n).stat().st_size > 0 for n in ['openvpn_user', 'openvpn_password']),
                'vpn_acceptance_current': (ROOT / 'vpn-accepted.json').exists() and json.loads((ROOT / 'vpn-accepted.json').read_text()).get('fingerprint') == fingerprint(cs),
                'downloads_free_bytes': os.statvfs(DOWNLOADS).f_bavail * os.statvfs(DOWNLOADS).f_frsize,
                'plex_library_count': len(libraries())}
    if action == 'libraries':
        return libraries()
    if action == 'search':
        query = a.get('query') or ''
        if not query.strip():
            raise ValueError('Provide a search query')
        root = ET.fromstring(plex('/hubs/search?' + urllib.parse.urlencode({'query': query, 'limit': 20})))
        return [{k: e.get(k) for k in ('ratingKey', 'title', 'year', 'type', 'grandparentTitle', 'parentIndex', 'index') if e.get(k) is not None}
                for e in root.iter() if e.tag in ('Video', 'Directory') and e.get('ratingKey')]
    if action == 'scan':
        s = section(a['section'])
        plex(f"/library/sections/{s['id']}/refresh")
        return {'scan_requested': s['title'], 'indexing_verified': False}
    q = QB()
    if action == 'torrents':
        return [{k: t.get(k) for k in ('hash', 'name', 'state', 'progress', 'amount_left', 'dlspeed', 'upspeed', 'ratio', 'save_path')} for t in q.json('torrents/info')]
    if action == 'files':
        return q.json('torrents/files?hash=' + torrent_hash(a))
    if action == 'add':
        guard(q)
        magnet = a.get('magnet') or ''
        if not magnet.startswith('magnet:?') or '\n' in magnet or '\r' in magnet or len(magnet) > 16000:
            raise ValueError('Provide one magnet URI')
        result = q.call('torrents/add', {'urls': magnet, 'savepath': '/downloads/complete', 'stopped': 'true', 'autoTMM': 'false'})
        added = {}
        if result.strip() not in (b'Ok.', b''):
            # 5.2 returns a structured result rather than the legacy "Ok.".
            added = json.loads(result)
            if added.get('success_count', 0) + added.get('pending_count', 0) < 1 or added.get('failure_count', 0):
                raise RuntimeError('qBittorrent did not accept the magnet; check the queue before retrying')
        return {'added_stopped': True, 'hashes': added.get('added_torrent_ids', []), 'next': 'List torrents, then start the matching hash'}
    if action in ('start', 'stop'):
        if action == 'start':
            guard(q)
        h = torrent_hash(a)
        if not q.json('torrents/info?hashes=' + h):
            raise ValueError('Torrent hash not found')
        q.call('torrents/' + action, {'hashes': h})
        return {'requested': action, 'hash': h}
    if action == 'import':
        return import_file(q, a)
    raise ValueError('Unsupported media operation')


if __name__ == '__main__':
    try:
        a = json.loads(sys.stdin.readline(32768))
        print(json.dumps(main(a), indent=2))
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc)}))
        sys.exit(1)
    except Exception as exc:
        # Do not expose API responses, tokens, or connection URLs in exception text.
        print(json.dumps({'error': type(exc).__name__, 'detail': 'Media operation failed; check private host configuration and service health'}))
        sys.exit(1)
