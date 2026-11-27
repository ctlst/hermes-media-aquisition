# Hermes media skills

Use Hermes to browse a Plex directory, import a completed film or show, or search for a game. Install only the skills you need into an existing Hermes installation.

| Where Hermes runs | What to copy | What the operator supplies |
| --- | --- | --- |
| On the Plex host, with ordinary networking | The everyday Plex or game-search skill. Add the host skill if you want a guided permission check. | The actual library path and the access you want to grant. Game search alone needs Python 3 and access to the index. |
| In a VM or container | The same everyday skills in the guest. Give the host skill to an agent on the media host if needed. | A guest-visible mount for file operations or an existing remote media integration. A read-only mount is enough for browsing. |
| Separate agent with VPN-isolated downloads | The everyday skills, plus the host skill if useful. | Your existing download integration, or the optional reference deployment with Gluetun, qBittorrent and a restricted SSH backend. |

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

## How our setup works

Our agent uses SSH to call a media backend on a separate host. That host runs the torrent client in a VPN container's network namespace, keeps the credentials locally, and hardlinks completed video files into Plex. The example includes the sanitized service unit, Compose file, Python scripts and optional Samba configuration. Its VPN guard applies only to that implementation. [Deployment and recovery instructions](examples/homelab/README.md)

See the [fresh VM walkthrough](docs/fresh-vm-test.md) for the access test and its limits.
