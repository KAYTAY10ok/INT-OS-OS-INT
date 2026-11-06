# Building the first INT image

Requirements: Python 3, Git, access to the local Docker socket, HTTPS through the
configured proxy, and a trusted CA bundle at `/etc/ssl/certs/ca-certificates.crt`.
The helper uses `unix:///var/run/docker.sock` explicitly. It preserves Docker's
registry/proxy configuration and mounts the current public trust bundle read-only.
The builder uses an Ubuntu 24.04 image pinned by digest and verifies APT signatures
and HTTPS. It runs BitBake as the caller's non-root UID/GID, never privileged.

The tested cloud instance has 5 visible CPUs and 33 GiB RAM. Builds use four jobs,
`rm_work`, and disk-monitor stop thresholds. The 60 GiB filesystem is constrained;
monitor it rather than deleting user data. `rm_work` discards per-recipe working
trees after packaging, so debugging one recipe may require rebuilding it.
Archive downloads prefer Yocto's official mirror with the recipe checksums
unchanged; Git fetches use shallow history at the pinned revision.
Native QEMU builds only x86-64, without its graphical/audio frontend. This matches
the serial-console milestone; graphical emulation needs an explicit later profile.

From the existing checkout (each cloud task is already isolated; do not create a
Git worktree unless explicitly requested):

```sh
./scripts/int bootstrap
./scripts/int builder
./scripts/int configure
./scripts/int check
./scripts/int build int-image-smoke
./scripts/int smoke
```

`bootstrap` fetches the exact revisions from `configs/sources.lock.json` and
refuses unexpected revisions or local upstream changes. `configure` creates
`bblayers.conf` and `local.conf` and refuses to overwrite differing files. All
sources, caches, build outputs and test artifacts go to `../int-linux-work` by
default. Set `INT_WORKDIR` consistently to use another path outside the checkout.
If a newer helper intentionally changes generated configuration, inspect and
update the generated files before rerunning configure; it will not overwrite
local edits automatically.

Private/local overrides belong in
`$INT_WORKDIR/build/conf/int-local.conf` (or the default sibling location).
Never commit credentials or password hashes. The foundation image has a locked
root account and no SSH server. Its smoke variant needs no login and deliberately
shuts down after its assertions. The newer core image adds interactive first-owner
enrollment on the console; passwords are entered through upstream `passwd`.

To build the console image without the smoke service:

```sh
./scripts/int build int-image-minimal
```

The shared console core has passed its VM milestone. Build and test its disposable
variant with:

```sh
./scripts/int build int-image-core-smoke
./scripts/int core-check
```

The core test drives real enrollment, login, password-authenticated sudo and
guest-only firewall probes. Its random password stays in memory; any password
echo fails the test and the retained transcript is redacted. The test preserves
the original unprovisioned inputs and uses QEMU's temporary disk overlay. Build
`int-image-core` for the corresponding console image without the test package.
Read the [core validation record](docs/development/validation-core-2026-11-05.md)
for the exact verified scope.
The kernel ABI is `6.18.54-int-core1`; keep kernel/modules/rootfs together.
The preserved Phase 1 evidence contains its own original matching artifacts.

Host tests require Python 3 and `pexpect` (provided in the builder and installed
explicitly by CI). They include simulated PTY conversations; only `core-check`
exercises the built guest. Run `python3 -m unittest discover -s tests -v`.

## Separate desktop development profile

The desktop smoke image has passed its headless VM gate. Its pinned meta-wayland
source is fetched by bootstrap. Use a separate configuration and output directory
while retaining the console build:

```sh
./scripts/int bootstrap
./scripts/int --profile desktop configure
./scripts/int --profile desktop check
./scripts/int --profile desktop build int-image-desktop-smoke
./scripts/int --profile desktop desktop-check
```

This uses `INT_WORKDIR/build-desktop`, with the common verified download/sstate
caches. The default `core` profile keeps `INT_WORKDIR/build` and its existing
configuration. Both profiles share the operation lock; run one operation at a
time. Desktop kernel/modules use ABI `6.18.54-int-desktop1`, revision `r2`, and
stay separate from the preserved console core. The QEMU prototype deliberately
omits unrelated Mesa hardware/LLVM drivers; this is not a physical-GPU profile.

The first desktop gate uses a rootless headless Sway session and a real Wayland
terminal. A separate disposable image now also tests the actual local logind/DRM
seat and Virtio VGA output:

```sh
./scripts/int --profile desktop build int-image-graphics-smoke
./scripts/int --profile desktop graphics-check
```

The latter records framebuffer captures and sends virtual keyboard events through
a private local QMP socket; see the [graphics validation](docs/development/validation-graphics-2026-11-06.md).
Neither test qualifies physical keyboards/mice, displays or GPU hardware,
accelerated rendering, or resource targets. The production command
`start-int-desktop` requires an active local virtual console session.

Images and manifests appear in
`../int-linux-work/build/tmp/deploy/images/qemux86-64/`.
QEMU evidence is retained in `../int-linux-work/evidence/`. The smoke runner uses
snapshots and keeps successful inputs as a known-good artifact. No disk is
formatted and no host port is forwarded.

Use `./scripts/int shell` for a builder shell with the OE environment loaded.
Run only one BitBake operation per work directory; separate containers have
separate process namespaces and must not share a live BitBake server.
Do not edit pinned upstream sources in place. To update, preserve local work,
review new metadata and kernel source revisions, then change the lock and layer
pins together and run the build/boot checks again. A pinned source graph does not
by itself establish bit-for-bit reproducibility; compare independent builds.

After an abrupt interruption, do not assume every partially generated object is
valid. A resumed build here found empty `.o` files and stale archives in CMake and
GCC. Preserve the failing logs, inspect the affected recipe's outputs, and remove
only confirmed damaged generated files or clean that one recipe before retrying.
Do not delete all downloads, sources or sstate to hide a failed compilation.
