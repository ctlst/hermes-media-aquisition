---
name: plex-torrent
description: Browse a Plex media directory and import completed files using local or mounted storage.
---

# Plex library work

Use the access already available to the agent. Ask which library and operation the person wants if ambiguous. For a listing request, use the local procedure below. If access is missing, hand the host operator the `plex-directory-setup` skill or ask them to expose the chosen directory. A local or mounted directory works for these steps even when there is no VPN, torrent client, Plex API token or SSH backend.

## Local or mounted directory

1. Confirm the visible library path and whether the person wants browsing or imports. List only the requested level, e.g. `find "$LIBRARY" -mindepth 1 -maxdepth 1 -printf '%f\n'` on Linux. Report a denied or missing path as observed. A filesystem listing proves file visibility; the Plex catalog has a separate indexing step.
2. For an import, resolve the existing completed source, library root, media type, title/year and desired name. Exclude samples and sidecars unless requested. Keep the file's real extension. For example, place a film at `Movies/Title (Year)/Title (Year).mkv` relative to the library parent.
3. Resolve the destination against the selected library root and reject absolute input, traversal and symlinks in the relative path. Check source type, destination conflicts and parent permissions. Create only the approved title or season folder. On the same local filesystem use a hardlink with no replacement, e.g. `ln -T -- "$SOURCE" "$DEST"` on Linux. If the name exists, check whether both names already identify the same inode. If hardlinks are unavailable, agree on a copy, check free space, and verify the copy before reporting completion. Keep the original.
4. For a requested catalog check or scan, use the existing Plex integration if configured, or have the library owner choose **Scan Library Files** in Plex Web. Verify the title appears in Plex. If only filesystem access is available, report the file operation and leave indexing unconfirmed.
5. Downloads in this setup use qBittorrent through Gluetun. Have the operator queue the chosen release in the configured Web UI if the agent has no authorized qBittorrent integration. A read-only library is sufficient for browsing. Importing requires permission to create the destination; report that requirement if the mount is read-only.

## Release lookup

The installed workflow uses title/year for films and title plus season or episode for shows. HTML detail pages can surface complete packs missed by RSS. Compare exact title, language, codec, season span, per-episode size and current peers. Inspect the file list before choosing the destination. Indexer seed counts are snapshots. Use the torrent's actual progress to report download status. A stopped or stalled torrent remains in the queue until the operator manages it.
