# Hermes, Plex and VPN downloads

```text
qBittorrent container → tun0 in the Gluetun container’s network namespace → VPN → peers

qBittorrent → /downloads → completed files on disk
Hermes → local directory or mounted share → Plex media files
```

**Downloads.** Run qBittorrent and Gluetun together on the Docker host. Gluetun owns the VPN tunnel and firewall. qBittorrent uses the same network namespace and binds torrent traffic to `tun0`. If the tunnel drops, the firewall blocks direct internet access and transfers stall. The host setup includes an empty-queue test that drops the tunnel while qBittorrent keeps running, checks that traffic is blocked, and verifies recovery. [Set up the containers](examples/homelab/README.md) · [Compose file](examples/homelab/compose.yml)

**Plex files.** The only choice is how Hermes reaches the media directory. Use the folder Plex scans for movies or episodes. The path visible to Plex inside its own container can differ from the path Hermes sees.

| Where the files live | What to give Hermes |
| --- | --- |
| Local to the machine running Hermes | The existing media directory, for example `/srv/media/Movies`. Run the access check as the Hermes user. |
| On a NAS, or outside the Hermes VM | Mount the library share where Hermes runs, for example at `/mnt/plex` inside the VM. Give Hermes the mounted path, such as `/mnt/plex/Movies`. Verify the source before using it. |

### Use the skills

From the unpacked release, copy the skills you need into the existing Hermes account. Start a new chat. For an existing skill, compare the files before replacing local edits.

```sh
skills="${HERMES_HOME:-$HOME/.hermes}/skills"
mkdir -p "$skills"
cp -R host/skills/plex-directory-setup "$skills/"
cp -R agent/skills/plex-torrent agent/skills/game-search "$skills/"
```

Ask Hermes: **“Walk me through giving you access to my Plex Movies folder. I want to browse it.”** Browsing needs read and traversal access. For importing, give Hermes access to the completed source file and write permission on the intended library destination. Use the download path visible to Hermes; `/downloads` is the path inside qBittorrent. Host SSH credentials are unnecessary for both storage layouts. [Directory walkthrough and VM test](docs/fresh-vm-test.md)

### How our VM calls the media host

In our deployment, Hermes can ask the media host to queue a torrent, import a completed file, or scan Plex. The VM sends a JSON request over SSH. The host associates the VM’s dedicated key with one fixed command that runs `media_backend.py` for that request. Systemd supervises the download containers separately. [Restricted SSH setup](reference/deployment/README.md#4-opt-in-to-backend-access-from-the-vm) · [Backend code](reference/deployment/media-host/media_backend.py)

The host enforces the restriction. The backend accepts a fixed list of actions and reads request fields as data. For example, a quote in a movie title stays part of the Plex search query. Anyone holding the private key can still perform the permitted actions, including stopping torrents and importing media. A mounted share has its own filesystem permissions.
