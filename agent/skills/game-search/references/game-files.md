# Game release formats and checks

## Formats

| Files | Meaning | Usable as is? |
| --- | --- | --- |
| `.nsp`, `.nsz` | Switch 1 digital package, `.nsz` compressed | Check reader support for the exact format |
| `.xci`, `.xcz` | Switch 1 cartridge image, `.xcz` compressed | Check reader support for the exact format |
| DNSP / DXCI | Switch 2 digital and cartridge dumps, successors of NSP and XCI | Check reader and title support |
| `.nup` | May contain title or update data | Check the manifest, title/build and target reader before deciding whether it is usable by itself. |
| `romfs/` + `exefs/` folders | Extracted game content | Some recompilation projects accept these directly |
| `.nx` | Community container bundling base, updates and DLC | Not a console format; needs its own tooling |
| `setup.exe` + numbered `.bin` parts | Windows installer wrapping the game | No. Inspect the manifest; extract only if asked |
| `.iso`, `.chd`, `.rvz` and similar | Disc images for other consoles | Match against the target emulator's supported list |
| `.nfo`, `.txt`, small `.exe` | Release notes and tools | Never execute |

Switch 2 games do not ship as XCI/NSP. A "Switch 2" release containing only those files, or that is far smaller than other dumps of the same game, is probably mislabelled. Check its internal title with a suitable tool before reporting it.

## Selecting the file

Run `files --hash "$HASH"` after `start` and choose the largest game file of the expected format, never blind index 0. A pack can mix base game, update and DLC; report each part and which ones the person needs.

## Inspecting an installer without running it

Inno Setup installers can be listed on Linux with `innoextract` (`apt install innoextract`):

```sh
innoextract --list setup.exe
innoextract -I "path/inside/manifest.md5" -d "$SCRATCH" setup.exe
```

The first command lists every file the installer would produce. The second extracts only a small manifest, which usually names the game file and its format and version. On an incomplete download, wait for completion before diagnosing the installer version. On a completed file, check the digest and whether the tool supports that installer.

Full extraction is a separate, explicit request. Some installers only finish under Wine. That runs Windows code, so ask the operator first, use a disposable environment on bulk storage, check free disk (often more than the download size again), and never run it from the seeded `complete/` directory.

## Handing off

Report the completed path, size, format, version if known, and any digest you verified. Companion tools the person asks for (an emulator AppImage, a launcher) can sit beside the game in the downloads directory, but run them on the person's own machine, not on the agent host.
