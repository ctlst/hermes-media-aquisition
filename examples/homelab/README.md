# Homelab example with qBittorrent and Gluetun

Steps 1–3 set up qBittorrent and Gluetun on the media host. Once the host checks pass, the operator can manage the queue locally at `http://127.0.0.1:18080` using the qBittorrent credentials created during bootstrap. [Compose file](media-host/compose.yml) · [Host setup and verification script](media-host/admin.py)

Step 4 is an independent choice to let Hermes call the media backend over restricted SSH. Step 5 shows our optional writable Samba shares. For an isolated VM that only needs to browse, export the chosen folder read-only. [VM walkthrough](../../docs/fresh-vm-test.md)

A Hermes agent can take a request such as “add this film to Plex” or “find the Linux edition of this game.” The two requests share a download client. A film ends up in a Plex library as a hardlink. A game search returns candidates, and a requested game download stays on the downloads share.

## What runs where

| Component | Job |
| --- | --- |
| Hermes agent | Resolves the request, searches for releases, chooses files, and runs the media client. Game and release searches use the agent’s network connection. |
| SSH client and backend | The client sends one JSON request on standard input. A dedicated key on the agent can invoke a fixed Python program on the media host. The program holds the allowed verbs and reads local credentials. |
| Gluetun and qBittorrent | qBittorrent joins Gluetun’s network namespace. Gluetun owns the VPN tunnel, firewall and localhost WebUI port. Torrent payload and peer traffic use this namespace. |
| Plex | The existing server scans its own libraries. The backend reads its API at `127.0.0.1:32400` and creates links on the host filesystem. |
| Samba | Two optional encrypted shares let Hermes read and write downloads and library files. Write access includes changing files directly; grant it only for the intended directories. |

## What came from the deployment

The media host directory contains sanitized copies of the **installed systemd unit**, **deployed Compose file**, **admin.py**, **media_backend.py**, **test_media.py** and the host’s Samba share definitions. The agent directory includes its deployed **media.py** SSH client and the host’s client-mount template. Hostnames, usernames, container names, datasets, mount paths, profile filename, timezone and the private WebUI port have coordinated example values throughout.

The earlier architecture guide described a reconstructed oneshot unit. The installed unit is **Type=simple**. Its preflight confirms both ZFS datasets using `findmnt`, checks private VPN credential files and validates Compose. Systemd supervises the foreground command `docker compose up --abort-on-container-exit`, retries after 15 seconds and calls `docker compose down` on stop. Both containers have Docker restart policy `no`. Compose waits for the health check provided by the Gluetun image. The running deployment uses a **custom OpenVPN TCP profile**.

The everyday SKILL.md files condense the deployed workflows for a new installation. **search_games.py** packages the original skill’s manual HTML lookup as a read-only command. **watch.py** adapts the installed progress monitor to accept exact hashes, replacing its private, hard-coded watch list. Live queues, media libraries, credentials, SSH keys, provider configuration and VPN acceptance records are site-specific. Generate or supply those on your own systems.

## Installation

Paths below assume you are in `examples/homelab/` in the unpacked release when copying files. Edit the client endpoint in the copy of `media.py` you install on the agent.

Use a Linux media host with ZFS, Docker Engine, the Docker Compose plugin, systemd and Python 3.9+. The Plex integration assumes an existing Plex server. The optional SSH integration in step 4 needs OpenSSH on both machines and Python on the agent. Samba on the host and cifs-utils on the agent are needed only for direct file access. The deployed VPN uses NordVPN service credentials and a provider-issued TCP OpenVPN profile. Other providers may require changes to the credential prompts, secret names or Compose configuration.

### 1. Set the site values

| Example in this archive | Where to set your value |
| --- | --- |
| `media-host.example`, account `mediaops` | Agent’s media.py and mount template. Use the media-host account in the unit, forced command and Samba force-user entries. |
| `tank/media` mounted at `/srv/media` | admin.py preflight, backend roots, Compose, Samba and the systemd mount dependency. Downloads and the Plex library must share one filesystem for hardlinks. |
| `tank/appdata` mounted at `/srv/appdata` | admin.py preflight, Compose and the unit. Container configuration lives below this mount. |
| `/opt/agent-media` | Install the host files here or change the unit and SSH forced command together. |
| Plex sees `/data/VIDEO` | Map the host library directory to this container path. Each managed section must have an existing subdirectory underneath it. For a different mapping update media_backend.py and test_media.py. |
| User/group IDs `1000:1000`, agent IP `192.0.2.20` | Set the actual media-file owner in Compose and the agent user's IDs in fstab. Replace the documentation IP in Samba with the agent’s LAN address. |
| WebUI `18080` | Keep it consistent in Compose, the backend URL, Referer and qBittorrent session-cookie name. Keep the published address on loopback. |

### 2. Prepare storage and private configuration on the media host

Use an operator account with Docker access. The unit runs as that account. Confirm the ZFS mounts before creating directories. A child ZFS dataset has its own filesystem even when it sits under the same pool.

```sh
findmnt -T /srv/media -o TARGET,SOURCE,FSTYPE
findmnt -T /srv/appdata -o TARGET,SOURCE,FSTYPE
```

After verifying those results, install the host files and create the directories. These example commands assume the accounts and datasets above already exist. Preserve the existing ownership and permissions on an established Plex library.

```sh
sudo install -d -m 0700 -o mediaops -g mediaops /opt/agent-media
sudo install -m 0644 -o mediaops -g mediaops media-host/* /opt/agent-media/
sudo install -d -o mediaops -g mediaops /srv/media/downloads/agent/{complete,incomplete}
sudo install -d -o mediaops -g mediaops /srv/appdata/agent-media/{gluetun,qbittorrent}
```

Run the brace-expansion commands in Bash. Ensure the operator can create library destinations and hardlink the downloaded files, and Plex can read the results. Compare the device numbers of the download and library directories with `stat -c '%d %n' /srv/media/downloads/agent /srv/media/library`.

Place your provider-issued profile at `/srv/appdata/agent-media/gluetun/provider.tcp.ovpn`. Include any referenced provider files in the bind-mounted directory. Run the following as the media operator. Enter the VPN service credentials privately at the prompt. The Plex token command is only for operators enabling Plex catalog queries or scans.

```sh
cd /opt/agent-media
python3 admin.py credentials
# Optional Plex integration
python3 -c 'from getpass import getpass; from admin import secret_file; secret_file("plex_token", getpass("Plex token: ").strip())'
python3 -m unittest -v test_media
python3 admin.py preflight
```

### 3. Bootstrap and test the VPN before adding downloads

On an initial empty stack, run the following as the operator in `/opt/agent-media`. The verifier needs working noninteractive sudo access for its `nsenter` network-namespace commands. Keep this privilege with the local operator. It is separate from the agent’s SSH interface.

```sh
python3 admin.py bootstrap
python3 admin.py verify
docker compose down
sudo install -m 0644 agent-media.service /etc/systemd/system/agent-media.service
sudo systemctl daemon-reload
sudo systemctl enable --now agent-media.service
systemctl is-active agent-media.service
python3 -c 'from media_backend import QB, guard; guard(QB()); print("VPN gate passed")'
```

Bootstrap configures qBittorrent with a random local password, binds it to `tun0` and sets the complete and incomplete directories. Verification compares host and VPN egress, checks a direct-interface request against a numeric destination, pauses Gluetun and drops the tunnel while qBittorrent is running, then recreates the pair and verifies recovery. It writes `vpn-accepted.json` locally after success. This is an intentional outage test for an empty queue with service supervision stopped.

The live guard on **add** and **start** checks Gluetun health, the current network namespace, the configured interface and the acceptance fingerprint. The fingerprint covers image identities and Compose text. Reverify manually after changing the contents of a bind-mounted VPN profile or firewall configuration. For a populated service, preserve the queue and use a maintenance plan or an isolated empty stack to validate changes. The original verifier explicitly requires an empty queue. The deployed image tags are mutable; record the deployed image IDs when testing.

### 4. Opt in to backend access from the VM

On the agent VM, copy the two skill directories into the agent account’s skills directory. Generate a dedicated key as that account if it does not already have one.

```sh
mkdir -p ~/.hermes/skills ~/.ssh
chmod 700 ~/.ssh
cp -R ../../agent/skills/plex-torrent ../../agent/skills/game-search ~/.hermes/skills/
cp -R agent/plex-backend/scripts agent/plex-backend/references ~/.hermes/skills/plex-torrent/
ssh-keygen -t ed25519 -f ~/.ssh/agent-media -C agent-media
```

The noninteractive client needs an unattended key or an available SSH agent. On the media host, append the following entry to the media operator’s `~/.ssh/authorized_keys`, replacing the sample key field with the new public key. Preserve other entries. The forced command shown here follows the installed key restrictions.

```text
restrict,command="/usr/bin/python3 /opt/agent-media/media_backend.py" ssh-ed25519 PUBLIC_KEY_FROM_AGENT agent-media
```

From a trusted administrator connection obtain the media host’s SSH host public key and fingerprint. Install its verified public key on the agent as a known-hosts line for the exact hostname in media.py, in `~/.ssh/agent-media-known-hosts`. Keep `StrictHostKeyChecking=yes`. The private SSH key stays on the agent. Test through the same entry point Hermes uses.

```sh
client="$HOME/.hermes/skills/plex-torrent/scripts/media.py"
python3 "$client" status
python3 "$client" libraries
python3 "$client" search --query "Example Film"
```

### 5. Mount the optional shares

Copy media-host/smb-shares.conf to the host’s Samba config directory and include it from smb.conf. Provision a dedicated local Samba account named `agent-media` with a private SMB password. Check that the account can reach only the intended shares. Run `testparm -s` and reload Samba after review. The force user must have the required filesystem access.

On the VM, create `/mnt/agent/downloads` and `/mnt/agent/library`. As root, create `/etc/samba/credentials-agent-media` with mode 0600 and the two lines `username=agent-media` and `password=YOUR_SMB_PASSWORD`. Add the two adapted entries from agent/mounts/downloads-and-library.fstab to the existing fstab and run `systemctl daemon-reload`. Start the corresponding automount units or mount each path explicitly. Use `findmnt -T /mnt/agent/downloads/complete` to confirm CIFS. Test with a disposable file and verify the library path is readable. Request hardlink imports through the backend on the media host.

## Try the workflows

**Plex.** First exercise the download path with a publisher-provided test magnet. List torrents, start its exact hash and confirm the selected file completed. For a movie or show, inspect the file list, select the actual media, import into a discovered section and scan. The companion skill contains the exact arguments for movies, multi-episode packs, subtitle files and indexing checks. A filesystem import and a Plex catalog match are separate results.

**Games.** Ask Hermes to “search for SuperTuxKart for Linux and list candidates.” This command exercises discovery without changing the queue:

```sh
python3 ~/.hermes/skills/game-search/scripts/search_games.py "SuperTuxKart" --platform Linux --details 3
```

A candidate is a source page, not proof of authenticity or availability. For a requested download, match the publisher, platform and contents first, then hand the chosen magnet to the existing media client. Return the completed file path on the share. Keep large extractions on bulk storage and verify the artifact before reporting it ready.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Service restarts every 15 seconds | Check the two ZFS dataset identities, the paths they cover, provider credentials and `docker compose config --quiet`. Review the unit journal locally. |
| VPN healthy yesterday; adding now fails | Inspect both container states, interface binding and acceptance. Recreate both containers together after a VPN container replacement. |
| Zero bytes left at 0% | Wait for metadata and numeric progress. The queue can report zero remaining before the client knows the files. |
| Import rejects the destination | Check section, actual file index, extension, source size, ownership and filesystem identity. A different existing destination is preserved. |
| Scan succeeds but title is missing | Check the Plex path mapping, permissions and naming, then query again after indexing. |
| Game search returns nothing | Check spelling/platform and inspect the indexer’s HTML for a layout change. Plex title search queries the local library. |
| Packed game fills the agent disk | Inspect the manifest and free space; budget for both input and expanded output on the media host. |

## Verification of this edition

The service and Compose behavior were checked against the deployed host. The included tests exercise the sanitized backend with fixtures. The search helper was exercised with a public game query. The bundle is a portable reference for an existing Plex installation; each recipient supplies their own storage, VPN profile, credentials and host trust, then runs their own first-activation test.
