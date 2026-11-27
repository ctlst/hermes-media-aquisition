# Hermes media skills

Use Hermes to browse a Plex directory, import a completed film or show, or search for a game. Install only the skills you need into an existing Hermes installation.

| Where Hermes runs | What to copy | What the operator supplies |
| --- | --- | --- |
| On the Plex host, with ordinary networking | The everyday Plex or game-search skill. Add the host skill if you want a guided permission check. | The actual library path and the access you want to grant. Game search alone needs Python 3 and access to the index. |
| In a VM or container | The same everyday skills in the guest. Give the host skill to an agent on the media host if needed. | For browsing, the operator exports one media folder read-only and mounts it in the guest. Online game search can run with no host share at all. |
| Separate agent with VPN-isolated downloads | The everyday skills, plus the host skill if useful. | Your existing download integration, or the optional reference deployment with Gluetun, qBittorrent and a restricted SSH backend. |

## Run Hermes in a VM without host SSH

For browsing, choose the Movies or TV folder you want Hermes to see. On the host, use your hypervisor to export just that folder read-only. Then mount it read-only inside the VM. An existing SMB share with a read-only server-side grant also works. The host operator handles the export. Hermes runs its checks from inside the guest as its ordinary user.

Tell Hermes: **“My Movies share is mounted at `/mnt/movies` in this VM. Use plex-directory-setup to verify it is the expected read-only share, then list the movie folders.”** Substitute your guest path. If the share is missing, Hermes gives the operator the next step. All host login credentials stay outside the VM. [Tested VM walkthrough](docs/fresh-vm-test.md)

If you want imports while keeping the library read-only in the VM, have the host operator perform the import. If Hermes needs to deliver files, you can give it a separate writable staging folder for that handoff. Online game search needs only the game-search skill and access to the index.

## Copy a skill

Run as the account that operates Hermes. The following assumes a fresh copy of each skill and that you are in the unpacked release directory. If a skill already exists, compare it before copying so local changes are preserved. Start a new chat after installing. For a host-access walkthrough, copy only the first skill. For a local Plex workflow with an already accessible media folder, copy only the Plex skill.

```sh
skills="${HERMES_HOME:-$HOME/.hermes}/skills"
mkdir -p "$skills"

# On the machine whose filesystem or mounts you want to inspect
cp -R host/skills/plex-directory-setup "$skills/"

# On the machine running the everyday Hermes agent (can be the same machine)
cp -R agent/skills/plex-torrent "$skills/"
cp -R agent/skills/game-search "$skills/"
```

If your host assistant uses a different skill directory, give it the entire `host/skills/plex-directory-setup/` folder. Keep the helper script alongside the skill. In a custom Hermes profile, resolve helper paths relative to the installed skill.

## Walk through directory access

1. Ask the host agent: **“Use plex-directory-setup. Can you walk me through giving Hermes access to my Plex folder?”**
2. Tell it the exact path and scope, for example: **“Hermes runs here. I only want it to list the Movies directory at /srv/media/Movies.”** If Hermes runs in a VM, tell it both the host path and the path mounted inside the VM, if known.
3. The agent checks as the intended user. If access is denied, it explains the smallest permission change the operator can make. Ask it to recheck after the change. Listing one directory does not establish permission to read every descendant or import a file.
4. For everyday use, try **“List the movie folders here,”** **“Import this completed film into Movies,”** or **“Find Linux releases of SuperTuxKart and show the candidates.”** Searching for games does not enqueue a download.

## Optional example: our SSH media backend

We chose to give our VM a dedicated SSH key so Hermes can request downloads, hardlink imports and Plex scans on the media host. The host restricts that key to one backend command. Anyone holding the key can request the media operations that backend permits. The Plex and VPN credentials stay on the host.

The SSH client, key setup, VPN containers and writable Samba configuration are packaged under `examples/homelab/`. Install this example only if you want that level of access. [Deployment and recovery instructions](examples/homelab/README.md)
