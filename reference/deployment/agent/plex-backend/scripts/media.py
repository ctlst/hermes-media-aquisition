#!/usr/bin/env python3
"""Hermes client: fixed SSH endpoint, structured stdin, no shell interpolation."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'libraries', 'search', 'scan', 'torrents', 'files', 'add', 'start', 'stop', 'import'])
    p.add_argument('--query')
    p.add_argument('--magnet')
    p.add_argument('--hash')
    p.add_argument('--section', type=int)
    p.add_argument('--file-index', type=int)
    p.add_argument('--destination')
    a = vars(p.parse_args())
    ssh = Path.home() / '.ssh'
    r = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                        '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
                        '-o', f'UserKnownHostsFile={ssh}/agent-media-known-hosts',
                        '-i', str(ssh / 'agent-media'), 'mediaops@media-host.example'],
                       input=json.dumps(a) + '\n', text=True, timeout=90)
    raise SystemExit(r.returncode)


if __name__ == '__main__':
    main()
