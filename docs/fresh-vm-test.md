# Walk someone through Plex directory access

Give the person who manages the media filesystem the `host/skills/plex-directory-setup` folder, including its Python helper. They can use it in an existing Hermes chat after copying it into their skills directory and starting a new session. The everyday Plex and game-search skills can be installed independently.

## What to say to Hermes

**You:** “Use plex-directory-setup. Can you walk me through giving Hermes access to my Plex media folder? One step at a time.”

Be ready to tell Hermes three things:

- Which folder contains the actual movies or episodes. In Plex Web, open the library’s edit dialog and look under **Add folders**. For a containerized Plex server, the host operator may need to translate that path through the container’s mount configuration.
- Where Hermes runs relative to the files. If it runs in a VM, give the host-side folder and the guest mount path if you know them.
- What Hermes should be able to do. Listing a folder needs less access than reading the video files below it or creating a new title folder.

**You, on the media host:** “The media folder is here at `/srv/plex-test/Movies`. Only the `hermes` user needs to list that directory. Check it as yourself, keep filenames private, and give me the owner command if access is denied.”

From the installed skill folder, Hermes can run `python3 scripts/check_access.py --local /srv/plex-test/Movies` as its ordinary service user. If the named directory denies listing, its ancestors permit traversal, and the filesystem supports Linux ACLs, the owner can grant that user list and traversal rights. The following example uses the test account and path. Check existing ACLs with `getfacl -p` first. A change to the ACL mask can affect other entries on directories that already have extended ACLs.

```sh
sudo setfacl -m u:hermes:r-x -- /srv/plex-test/Movies
```

**You:** “I ran it. Check again as Hermes. Can you list it? Can you write there?”

For a real installation, stop when the requested access works. When the owner wants to remove a newly added named grant, the corresponding command is `sudo setfacl -x u:hermes -- /srv/plex-test/Movies`. If that user already had a named entry, restore the previous ACL instead.

**You, in a VM:** “The media is on the host. I expect it at `/mnt/plex-test` inside this VM. Check whether the host share is actually mounted there before telling me we have access.”

The host skill includes a Linux mount check. From the installed skill folder, run `python3 scripts/check_access.py --mountpoint /mnt/plex-test /mnt/plex-test`. For a subdirectory, keep the first argument at the share root and change the second to the directory being checked. Compare the reported source with the export you intended to share. Hermes can inspect the mount and explain the next step to the person who controls the host or guest. An empty directory on the VM’s root filesystem can pass a listing check. Match the mount source and filesystem to the intended export, then run the permission check on the guest path. Read-only access is sufficient for browsing.

## Fresh VM test environment

We used a disposable Ubuntu 24.04.5 KVM guest with 2 vCPUs, 3 GiB of RAM and a 20 GiB thin virtual disk. After installing Hermes, the root filesystem reported 4.6 GiB used. The inference server ran outside the guest. This measures a conventional KVM guest with externally served inference. A microVM and lower memory limits need their own tests.

Hermes Agent revision `8fc0374447` ran under the unprivileged `hermes` account. We copied exactly one custom skill and its helper. The guest had no credentials for Plex and no everyday skills from this repository. The Ubuntu image needed the `libatomic1` package for the agent installer and `acl` for the owner’s permission change. We used a synthetic library and a separate disposable host export.

## What happened in the chat

The first attempt suggested `chmod 755`, which would also grant access to other users. We left the permissions at 0700, updated the skill to require a grant scoped to the requested user, and added a diagnostic hint to the helper.

In the repeat session, Hermes opened the skill and asked for the path, the machine and the user. It inspected the path and gave the operator `setfacl -m u:hermes:r-x /srv/plex-test/Movies`. It initially tried to invoke the helper through sudo. The unprivileged account had no sudo access. When prompted to run the helper directly, Hermes observed `Permission denied`. The skill now explicitly directs Hermes to check its current identity and distinguishes a sudo failure from a directory access result.

The operator applied the named ACL. Group and other permissions stayed at `---`. The permission fields from the helper, run as Hermes, were:

```json
{"user":"hermes","directory":"/srv/plex-test/Movies","can_list":true,"can_traverse":true,"can_write_and_traverse":false}
```

In the initial VM mount test, Hermes saw the guest root disk in the mount table and incorrectly reported that the share was mounted. We added an explicit expected mount point to the helper. A repeat run skipped the optional check, so the released helper requires a choice between `--local` and `--mountpoint`. If the kernel reports a different containing filesystem, the helper exits with status 2 before attempting a listing. The mount test uses a read-only QEMU 9p export named `plexsample`.

With the share detached, the revised skill prompted Hermes to use the mount check. The helper reported an actual target of `/`, filesystem `ext4`, and exit status 2. Hermes told the operator, “the host folder is not accessible at the path you specified,” and asked them to identify and mount the correct export.

For this disposable QEMU guest, the host operator had attached a sandbox directory using the following VM launch option. Set `SAMPLE_DIR` to a dedicated test directory on the host. Use your existing share protocol on an established system. The optional homelab example documents Samba.

```sh
-virtfs "local,path=$SAMPLE_DIR,mount_tag=plexsample,security_model=none,readonly=on"
```

The guest operator mounted that export and asked Hermes to recheck:

```sh
sudo mkdir -p /mnt/plex-test
sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro plexsample /mnt/plex-test
```

In the same chat, Hermes ran the helper again with the expected mount point. It identified source `plexsample`, filesystem `9p` and a read-only mount. Its reply included “You can list and traverse the directory (read-only access).” The helper reported `can_write_and_traverse: false`. This exercise verified directory browsing with a sample file. Plex indexing, media imports and torrent acquisition were outside this VM test.
