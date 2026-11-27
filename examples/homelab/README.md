# Run qBittorrent through Gluetun

Run these steps on the Linux Docker host with Docker Engine, Compose v2 or later, and `/dev/net/tun`. The example uses a provider-issued OpenVPN TCP profile with service credentials. The host’s normal internet connection and Plex’s storage location are independent of this stack.

### 1. Start the containers

In a fresh copy of `examples/homelab/`, set the absolute path to an **existing** download folder writable by the user who will own the files. If it lives on external storage, verify that storage is mounted first. This path appears as `/downloads` in qBittorrent. Run the following as that file owner with Docker access.

```sh
umask 077
mkdir -p gluetun
cp /path/to/your/provider.tcp.ovpn gluetun/provider.tcp.ovpn
printf 'DOWNLOAD_DIR=%s\nPUID=%s\nPGID=%s\n' /srv/downloads "$(id -u)" "$(id -g)" > .env
./setup.sh
```

Replace `/srv/downloads` with your directory. Copy any certificates the profile references into `gluetun/` and use paths under `/gluetun` in the profile. The script prompts privately for missing VPN credentials, writes them under `secrets/`, and waits for the containers to start. qBittorrent starts after Gluetun reports healthy. [Compose file](compose.yml) · [Gluetun container networking](https://github.com/qdm12/gluetun-wiki/blob/main/setup/connect-a-container-to-gluetun.md)

### 2. Bind qBittorrent to the tunnel

Open **http://127.0.0.1:18080** on the Docker host. On first use, sign in as `admin` with the temporary password from `docker compose logs qbittorrent` and set a permanent password. Read the logs privately. In **Tools → Options → Advanced → Network interface**, select **tun0** and save. Reopen that setting to confirm it persisted. Under **Downloads**, set the default save path to `/downloads`. [qBittorrent container documentation](https://docs.linuxserver.io/images/docker-qbittorrent/)

Gluetun publishes the Web UI on host loopback. Its firewall blocks ordinary internet egress outside the tunnel. Binding qBittorrent to `tun0` also confines its peer connections to that interface. The Compose example disables IPv6 in the shared network namespace and uses an IPv4 VPN. [Gluetun firewall settings](https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/firewall.md)

### 3. Test a VPN outage before adding torrents

Run this on the **new stack with an empty queue**. The `--empty-queue` flag is your confirmation of that; the script does not inspect the queue. The test intentionally interrupts its VPN and recreates both containers. It needs local sudo for `nsenter` and `ip`.

```sh
./verify-vpn.sh --empty-queue
```

The script checks the shared namespace, confirms that a numeric HTTPS destination works through the VPN, and tests the direct interface. Then it pauses Gluetun’s recovery process, takes `tun0` down, and probes again from the still-running qBittorrent container. Both default and direct-interface connections must fail. After recreating both containers it checks normal egress again. Queue downloads after the test passes. Recheck after changing the network configuration. [Test script](verify-vpn.sh)

To start the pair again after a host reboot, run `docker compose up -d --wait` here. If an interrupted test leaves the stack paused, unpause Gluetun and recreate both with `docker compose up -d --force-recreate --wait`.

### Give Hermes the Plex path

- **Local data:** Point Hermes at the existing Plex media directory, for example `/srv/media/Movies`.
- **NAS data or Hermes in a VM:** Mount the chosen export on the machine running Hermes. For example, for an existing read-only NFS export, the Linux operator can run `sudo mkdir -p /mnt/plex` and `sudo mount -t nfs -o ro nas.example:/export/plex /mnt/plex`. Substitute your NAS and export, or use your existing SMB or hypervisor share. In the guest, verify `findmnt -T /mnt/plex/Movies -o TARGET,SOURCE,FSTYPE,OPTIONS` shows the expected share. Give Hermes `/mnt/plex/Movies`. For imports the export and mount must allow writes to the chosen destination.

The operator mounts storage. Hermes checks access as its own user. [Guided directory check](../../docs/fresh-vm-test.md)
