# Shared desktop prototype validation — 2026-11-06 UTC

The shared desktop smoke image builds and passes its first real headless VM
test. This is an intermediate development milestone, not a release or proof of
physical display, GPU, keyboard, mouse or interactive launcher compatibility.

## Build and source configuration

The desktop profile uses the pinned meta-wayland revision
`2b97daa23e0e612a087ea54b150bd0b8e0ff9378`, Sway 1.11, wlroots 0.19.3,
foot 1.26.1, fuzzel 1.14.1 and Mesa 26.0.5. Its kernel ABI is
`6.18.54-int-desktop1`, recipe revision `r2`. The console profile and its
independently preserved `-int-core1` artifacts remain separate.

```sh
./scripts/int --profile desktop configure
./scripts/int --profile desktop check
./scripts/int --profile desktop build int-image-desktop-smoke
./scripts/int --profile desktop desktop-check
python3 -m unittest discover -s tests -v
```

The effective metadata check passed, including the stable compositor versions,
generic x86-64 CPU flags, Mesa QEMU profile and logind seat configuration. The
final smoke image build completed all 4,513 tasks, with 4,477 reused. The separate
non-test desktop image completed all 4,417 tasks, with 4,393 reused. The host
suite passed 71 tests. These tests are not physical performance measurements.

## Headless VM result

Successful evidence:
`INT_WORKDIR/evidence/qemu-smoke-20261106T102535.306207Z-e7d97f992755/`.
The run retains `result.json`, `known-good.json`, redacted serial output and
exact unprovisioned input copies. All 13 assertion groups passed; QEMU exited 0
after guest poweroff, with no timeout or credential echo. Owner UID was 1000,
and sudo rejected an incorrect password before accepting the correct one.

As the enrolled unprivileged owner, the test starts the actual Sway compositor
using the headless backend and Pixman, validates its selected configuration and
an active 1280×720 virtual output, checks Wayland protocols, validates foot and
fuzzel configuration, and confirms that a real foot terminal maps a nonempty
window and runs its child as the owner. It then verifies clean compositor exit.
The inherited core test also exercises firewall packet controls, network failure
and recovery, DHCP, login, password-authenticated sudo and clean shutdown.

| Tested input | Bytes | SHA256 |
| --- | ---: | --- |
| Kernel | 13,870,080 | `20b5d70671b202fc984dcb9d530361c95a52089f467978cc489a52ecccc14c37` |
| Smoke rootfs ext4 | 309,103,616 | `1e00e7eaaed71c3fa6dc20dc52401345782ac687f5877987de18acbe2de0b328` |
| Smoke manifest | 7,291 | `263f26caa1ba2d0e6fa37dc3ce24d58d8908f56f59e08f40b90517035f1eb79d` |

The full run took 60.596 seconds, including enrollment, network controls and
authentication. It is not a boot-time benchmark. QEMU TCG used qemu64, 512 MiB
RAM, two vCPUs, restricted networking and no host port forward. The temporary
disk overlay and in-memory test password do not alter the retained input image.

The non-test desktop image contains 235 packages. Its ext4 filesystem is
296,164,352 bytes, SHA256
`b080501bdd9dbb6e944a3e7ee0866a715e4493a3f5c1d54012761521a779f326`.
Its tar.zst archive is 70,545,426 bytes. An offline archive/manifest audit found
root locked, no preconfigured test owner or test helpers, and the expected Sway,
foot, fuzzel, UTF-8 locale and session launcher. Copies of the production kernel,
rootfs, archive, manifest, SPDX SBOM and audit report are retained under
`INT_WORKDIR/evidence/desktop-artifacts-20261106T102905Z/`. The complete VM test
used the smoke variant; the production image has not had a separate graphical
seat or interactive login test. Filesystem sizes are not memory benchmarks.

## Failures and fixes

- The first build reported an allarch packagegroup depending on dynamically
  renamed `dbus`. The group now uses the image machine architecture before
  inheriting the packagegroup class. The original log is retained under
  `desktop-build-failure-20261106T101503Z`; checks were not bypassed.
- The first VM started Sway but foot could not use the non-UTF-8 C locale. The
  desktop image now includes `en_US.UTF-8`; its wrapper preserves an existing
  UTF-8 user locale and otherwise selects a character-encoding fallback. The
  test uses the same available locale. Run:
  `qemu-smoke-20261106T101637.910752Z-059cfeb10c34`.
- The second VM mapped the terminal but Sway closed its IPC connection before
  replying to the exit command. The test now requires the compositor to exit
  successfully within its deadline, rather than requiring a reply after shutdown.
  Run: `qemu-smoke-20261106T102303.487139Z-60fdbe52affb`.

Both failed runs retain redacted diagnostic results and are not known-good.
No screenshot, input-device interaction, DRM/EGL seat, physical hardware,
accessibility or resource/performance qualification is claimed by this result.
The console core's earlier evidence is in
[validation-core-2026-11-05.md](validation-core-2026-11-05.md).
