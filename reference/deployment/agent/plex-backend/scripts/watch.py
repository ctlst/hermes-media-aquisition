#!/usr/bin/env python3
"""Report completion once per requested torrent hash."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("hash", nargs="+")
    args = p.parse_args()
    pending = {h.lower() for h in args.hash}
    if not all(re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", h) for h in pending):
        p.error("Pass full torrent hashes")
    client = Path(__file__).with_name("media.py")
    while pending:
        result = subprocess.run([sys.executable, str(client), "torrents"], capture_output=True, text=True, timeout=100)
        if result.returncode:
            sys.exit("Torrent list unavailable. Check media.py status and rerun the watcher.")
        torrents = {item["hash"].lower(): item for item in json.loads(result.stdout)}
        missing = pending.difference(torrents)
        if missing:
            sys.exit("Queue is missing " + ", ".join(sorted(missing)))
        for h in sorted(pending):
            item = torrents[h]
            if item["progress"] >= 1 and item["amount_left"] == 0 and "checking" not in item["state"].lower():
                print(f"DONE {h} {item['name']}", flush=True)
                pending.remove(h)
        if pending:
            time.sleep(60)

if __name__ == "__main__":
    main()
