# Release selection and queue checks

## Reading an index

- Search by `Title Year 1080p` for films and `Show S01 1080p` or `Show Complete` for TV. An HTML search page often shows season and series packs that an RSS feed of the same query misses.
- On a detail page, take the infohash, total size, seeds/leechers and the file list. Some pages put the label in its own tag, as in `<span>Seeds:</span> 76`, and use `&nbsp;` between number and unit. Flatten the HTML to text and normalise whitespace before matching. The `game-search` helper does this for one index.
- The file list confirms episode count, per-episode size, extensions and samples before you commit.
- Prefer the publisher's full magnet. A bare `magnet:?xt=urn:btih:HASH&dn=Name` can take a long time to find peers. If you must build one, add only public trackers the person or the publisher lists.

## Choosing

| Signal | Use it this way |
| --- | --- |
| Size budget | Respect the person's range. An old title may have no healthy release in range; show the available alternatives before queueing. |
| Codec | HEVC/x265 is roughly 40–50% smaller than H.264 at similar quality. Clients without HEVC decode make Plex transcode. |
| Seeds | Skip one or two seeds. Very high counts on small same-name items are often stale mirror entries. Live state after `start` is the real test. |
| TV packs | One healthy season or full-series pack beats many single-episode torrents. Otherwise use one release group consistently. |

## After `start`

- `downloading` with a nonzero `dlspeed` means the swarm is live.
- `metaDL` or `stalledDL` at progress 0 and zero speed can indicate an inactive swarm or connectivity problem. Check the VPN and peer availability before replacing the release.
- `queuedDL` means qBittorrent is waiting for a free download slot. A small film can sit behind a large TV pack.
- The listing may return `null` for size, seeds and downloaded bytes. Use `progress` and `amount_left`. Before metadata arrives `amount_left` can read 0 at progress 0; that is not completion.
- An `add` error often means the same hash is already queued, for example from an interrupted session. Check `torrents` for the hash before diagnosing the host.
- To switch releases, `stop` the old hash before starting the new one.

## TV and anime numbering

- Map each file index to its `SxxEyy` token. Build the table before importing and keep each file's extension; one pack can mix `.mkv` and `.mp4`.
- A merged two-part episode can make a pack hold one file fewer than the episode count. Match against the Plex numbering scheme rather than padding.
- Anime packs can use absolute numbers (`13`–`25` for season 2) or put a split final season in one torrent as `S04E01`–`E30`. Resolve the mapping with the person or the Plex agent's ordering before importing.
- Health beats group consistency when one group's season is dead.
- After the batch, check on-disk counts and look for duplicate episode numbers before reporting.
