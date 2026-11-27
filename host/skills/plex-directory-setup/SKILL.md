---
name: plex-directory-setup
description: Walk an operator through giving Hermes scoped access to a Plex library directory, check access as the intended user, and diagnose host, VM or container path differences.
---

# Set up Plex directory access

Start with the person's request. For “Can you give Hermes access to my Plex folder?”, ask for the exact directory, where Hermes runs relative to the files, and whether they want to browse or import. Use details they already gave. If someone asks to be walked through setup, give the next actionable step and wait for its result before proceeding. For a permission check, keep filenames out of terminal output and chat. Use the helper and path-specific metadata commands such as `stat -- /exact/path` or `namei -l -- /exact/path`. Listing a parent exposes sibling names.

## Choose the check

Use exactly one mode. For a physical host folder requested from inside a VM, run the mount check first. No other listing can establish host folder access.

```sh
# Host folder expected at this mount inside the VM
python3 scripts/check_access.py --mountpoint /expected/share /expected/share

# Media files confirmed to live on this same machine
python3 scripts/check_access.py --local /absolute/library/path
```

Run these from the installed skill folder. Substitute the operator’s paths. If the share root is unknown, ask where it should be mounted.

## Locate the right path

- **Same host.** Use the media folder that the library section scans and the account that runs Hermes. If the person does not know the path, have them open the library’s Edit Library → Add folders screen in Plex Web and read the configured folder. A Plex application-data or database directory serves a different purpose. If Plex runs in Docker, its library path may be a container destination. A host operator can run `docker inspect --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}' CONTAINER` to map it. Inspect only mounts.
- **Agent in a VM or container.** A host path is visible inside the guest only if mounted there. Ask for the expected guest mount root or the existing remote service they want to use. To check a share on Linux, run `python3 scripts/check_access.py --mountpoint /expected/share /expected/share/or/subdirectory` from the skill directory. Stop on a nonzero exit. If the target does not match, report the share as unmounted at that path and ask the operator to mount it. A successful local listing cannot override a mount mismatch. On a match, compare the reported source to the intended export. Check the reported target, source, filesystem and options with `findmnt -T /guest/path -o TARGET,SOURCE,FSTYPE,OPTIONS`. An ordinary directory on the guest root filesystem can exist at the expected path before the share is mounted. Confirm the mount is the intended share before treating the directory check as evidence of host access. If setup is needed on a different machine, give that operator one scoped instruction. For browsing, prefer a read-only mount. Imports need write access to the chosen destination or a host-side import service.
- **Agent assisting a different user.** Run `id -un` first. When the current shell already runs as the agent user, invoke the helper directly without sudo. A sudo error means the helper did not run. Running as root or a host administrator can give a false pass. A host operator can run the check for the service user with `sudo -u AGENT_USER -- python3 /readable/path/check_access.py --local /absolute/library/path`.

## Check before granting

Run the bundled `scripts/check_access.py` with the exact absolute directory using the Hermes terminal. It attempts to enumerate one entry and reports traversal, listing and effective write permission without printing names or creating files. It exits 0 on readable, 1 on denied and 2 on missing or invalid path. Report the identity and the observed result. A successful check at the library root covers only that directory.

If denied on Linux, inspect `namei -l /absolute/library/path` and, if installed, `getfacl -p /absolute/library/path`. When the requested grantee is one user, preserve access for the group and everyone else. Never suggest `chmod 755`, `chmod a+rx` or a recursive change to satisfy a single-user request. If the filesystem lacks named ACLs, ask the owner about an existing scoped share or dedicated group. For a read-only directory listing, its owner can run `setfacl -m u:AGENT_USER:r-x -- /absolute/library/path`. Ancestors need traversal; grant just `--x` on a blocking ancestor if required. Reading existing files beneath a directory may need separate file or subdirectory ACLs. For imports, discuss write access to the destination directory and read access to the specific source. Present permission-changing commands to the person administering that filesystem; apply only the change they authorize. Avoid recursive ownership or permission changes. Re-run the same check as Hermes and report the result.

Local browsing works with an accessible directory. Plex API credentials are used for catalog operations such as querying or triggering a scan. A VPN and download client are choices for acquisition. Install or configure these only when the person chooses them.
