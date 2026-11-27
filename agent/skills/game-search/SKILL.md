---
name: game-search
description: Find games by title and platform, inspect candidate releases and identify completed game files on the downloads share.
---

# Find a game

1. Resolve title, edition, platform and desired artifact. For Switch and Switch 2, distinguish the platform explicitly. For a local lookup search the completed share first. Use the directory the person supplied. For example, `find "$GAME_LIBRARY" -maxdepth 3 -iname '*supertux*'`.
2. Search the indexer's HTML pages by title and platform. Run `python3 "${HERMES_HOME:-$HOME/.hermes}"/skills/game-search/scripts/search_games.py "SuperTuxKart" --platform Linux --details 3`. The helper lists candidate titles and detail URLs. With `--details 3`, it also reads size, seed count and infohash for the first three when the index supplies them. A search-only request ends with the results. A missing result can reflect a changed index or unavailable site.
3. Read each promising detail page. Verify title/platform, edition, file list, published size, seed count and infohash. The deployed site wraps field labels in spans and sometimes separates sizes with nonbreaking spaces. Compare the hash with the original publisher's magnet when available. An infohash identifies torrent content; trust in the publisher is a separate check. Prefer the publisher's full magnet including its trackers.
4. Distinguish a directly usable game image, a patch requiring a base game, a multi-part archive and an installer. For example, `.nsp` and `.xci` commonly indicate Switch packages; a `.nup` needs a compatible reader and matching title/build. Confirm contents with the target runtime or a manifest. List any prerequisites.
5. Search requires only Python, network access to the chosen index and the bundled helper. If the person requests a download, use their configured client and network policy. If they use the example VPN backend, use the companion `plex-torrent` skill's `status`, `add`, `start`, `torrents` and `files` commands. Wait for the torrent and selected files to finish. A preallocated file can show its final size before it is complete.
6. Report the verified file in the operator's chosen local or mounted directory. Games stay outside Plex. Leave source files in place for seeding. For a packed release, inspect the manifest and plan space for inputs, expanded output and scratch files on bulk storage. Keep large staging directories off the agent VM root disk. Where the publisher supplies a digest, verify it before handing off an extracted file.
