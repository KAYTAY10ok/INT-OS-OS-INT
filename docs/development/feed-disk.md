# Disposable fixture disk

`scripts/feed-disk.py` can place a generated fixture directory and its
manifest in a new EXT4 image for a future virtual-machine test. It verifies
that the tree has exactly the manifest's bounded set of regular files and
that their sizes and SHA-256 hashes match. It does not establish that the
manifest or public key is authentic, verify signatures, or run DNF.

With `mke2fs` on `PATH`, create the parent output directory first and choose a
new output name outside the fixture tree:

```sh
mkdir -p ../int-linux-work/feed-disks
python3 scripts/feed-disk.py ../int-linux-work/feed-fixtures/NAME \
  ../int-linux-work/feed-disks/NAME
```

The new directory contains `feed.ext4` and `report.json`, including the image
and source-manifest hashes. An existing destination is never reused; a failed
run can leave an incomplete destination for inspection. The image is marked
read-only on the host. `scripts/qemu-feed-check.py` (through
`./scripts/int --profile feed feed-check`) attaches it as a second virtio
disk with `readonly=on` and, before and after each case, requires its hash to
match both `report.json` and an independently supplied `--feed-sha256`. The
guest service mounts it read-only and pins the full signing-key fingerprint
from the kernel command line, not from the disk. Neither has been run yet; see
[feed-vm-plan.md](feed-vm-plan.md).

Host-only tests cover manifest/path checks. On hosts with both `mke2fs` and
`debugfs`, they also construct a synthetic EXT4 image and inspect a file within
it. No guest or signed-feed result is claimed by these tests.
