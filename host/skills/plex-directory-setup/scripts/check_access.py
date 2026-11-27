#!/usr/bin/env python3
"""Check listing access without disclosing filenames or probing by writing."""
import argparse
import json
import os
import platform
import pwd
import shlex
import subprocess
import sys
from pathlib import Path


def check_mount(path, expected):
    """Match the filesystem containing path against the operator's expected mount root."""
    query = subprocess.run(
        ["findmnt", "--json", "--target", str(path), "--output", "TARGET,SOURCE,FSTYPE,OPTIONS"],
        capture_output=True, text=True, check=True,
    )
    mount = json.loads(query.stdout)["filesystems"][0]
    return {
        "expected_target": str(expected),
        "actual_target": mount["target"],
        "source": mount["source"],
        "filesystem": mount["fstype"],
        "read_only": "ro" in mount["options"].split(","),
        "target_matches": Path(mount["target"]).resolve() == expected.resolve(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true", help="Check a directory known to live on this machine")
    mode.add_argument("--mountpoint", type=Path, help="Expected guest mount root for a host share (Linux)")
    args = parser.parse_args()
    path = args.directory
    if not path.is_absolute():
        parser.error("Use an absolute directory path")
    result = {"user": pwd.getpwuid(os.geteuid()).pw_name, "directory": str(path)}
    if args.mountpoint is not None:
        if not args.mountpoint.is_absolute() or args.mountpoint.resolve() == Path("/"):
            parser.error("Use the absolute guest mount root of the intended share")
        try:
            result["mount"] = check_mount(path, args.mountpoint)
        except (OSError, subprocess.CalledProcessError, ValueError, KeyError, IndexError) as exc:
            result["error"] = f"Could not verify the mount: {exc}"
            print(json.dumps(result))
            return 2
        if not result["mount"]["target_matches"]:
            result["error"] = "Expected share is not mounted at this path. Host folder access is unverified."
            print(json.dumps(result))
            return 2
    else:
        result["scope"] = "Directory permissions only. Mount identity was not checked."
    try:
        with os.scandir(path) as entries:
            next(entries, None)
        result["can_list"] = True
        result["can_traverse"] = os.access(path, os.X_OK)
        result["can_write_and_traverse"] = os.access(path, os.W_OK | os.X_OK)
        status = 0 if result["can_traverse"] else 1
    except OSError as exc:
        result.update(can_list=False, error=exc.strerror)
        status = 1 if isinstance(exc, PermissionError) else 2
        if status == 1 and platform.system() == "Linux":
            result["next_check"] = shlex.join(["namei", "-l", "--", str(path)])
            result["owner_guidance"] = (
                "If the target directory denies listing and its ancestors permit traversal, "
                "the owner can grant only this user access with "
                + shlex.join(["setfacl", "-m", f"u:{result['user']}:r-x", "--", str(path)])
                + ". Preserve group and other access."
            )
    print(json.dumps(result))
    return status


if __name__ == "__main__":
    sys.exit(main())
