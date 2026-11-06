# Graphical console prototype validation — 2026-11-06 UTC

The shared desktop now passes graphical QEMU tests using a local tty1 session,
PAM/logind, Virtio VGA and a virtual keyboard. This is a virtual-machine
milestone, not a physical-hardware, mouse or performance qualification.

## Virtual keyboard and launcher

The later successful run is retained at
`INT_WORKDIR/evidence/qemu-smoke-20261106T110314.911138Z-5225d290d241/`.
All 15 check groups pass, with no credential echo or timeout and QEMU exit 0.
It retains the exact unprovisioned inputs, serial output, result and known-good
record. The host suite passed 75 tests. The 66.49-second complete run includes
enrollment, firewall, authentication and desktop checks; it is not a benchmark.

The test installs the virtio-input module in the disposable image and sends
actual QMP keyboard events through the emulated Virtio keyboard. `Super+Return`
opens a real foot terminal as the owner; `Super+D` opens fuzzel. The test types
`foot`, presses Return and verifies that a second terminal window belongs to the
owner. It validates and hashes two 1280×800 framebuffers and requires a visible
change when the launcher opens. The [launcher preview](evidence/launcher-2026-11-06.png)
is a lossless conversion of the retained capture, with SHA256
`acfb681ba9752d7185004c634012483f9ff14efa0b3a2e71aa97846c402131ea`.
The original `graphics.ppm` and `launcher.ppm` hashes are
`c804f40561e95df0ce2783a567c8c033e07aa7ee6950216a93a26e858b0add58` and
`44b147b00cfd8ebf472b671064773fa1d824ad513c7a27405d0d0bc8e71932d4`.
Only the named virtual-keyboard paths and application selection were exercised;
other shortcuts, physical keyboards and mice require further testing.

```sh
./scripts/int --profile desktop build int-image-graphics-smoke
./scripts/int --profile desktop graphics-check
python3 -m unittest discover -s tests -v
```

The image build completed all 4,532 tasks, with 4,489 reused. The host suite
passed 74 tests. Successful guest evidence is retained at
`INT_WORKDIR/evidence/qemu-smoke-20261106T104648.832223Z-1ef6afc521f7/`.
The runner reports all 14 check groups passed, no credential echo, QEMU exit 0,
and clean guest poweroff. Its complete 60.571-second run is not a boot benchmark.

After the already-tested first-owner enrollment, network/firewall and headless
desktop checks, a test-only root helper creates a separate PAM session for the
owner on tty1. The actual `start-int-desktop` wrapper requires that session to
be local, active, owned by the correct UID and on seat0. Sway then starts as
the owner through logind with the DRM backend, a Virtio VGA device and the
Pixman software renderer. The test checks for an active non-headless output,
uses Sway IPC to open a real foot terminal, verifies its visible geometry and
process UID, and requires clean session exit. The original tty1 getty is restored.

QMP is restricted to a private Unix socket inside the per-run evidence directory.
It records `graphics.ppm`, validated as a bounded, non-uniform 1280×800 image;
the result contains its SHA256
`b95c6107fb96bda9780dacc34207c527f8d82011cc59dc3f048c0a8c06f85681`.
The [PNG preview](evidence/graphics-2026-11-06.png) is a lossless conversion of
that capture, with SHA256
`76b13fc1281489544b7b8e035066c91dc1f2091c00f66f18833b9a2b0dd246be`.
This synthetic session displays no personal data or password. The exact unprovisioned kernel,
rootfs and manifest copies, redacted serial log, `result.json` and
`known-good.json` are retained with the image. QEMU uses a temporary disk
snapshot, TCG/qemu64, 512 MiB RAM, two vCPUs and no forwarded host ports.

The image `int-image-graphics-smoke` contains a root-owned test helper. It is
separate from the non-test `int-image-desktop`; do not install that helper in a
deployment image. A preliminary lab run showed the graphical output but failed
its cleanup assertion because a completed transient unit was already unloaded.
The reproducible test instead keeps the unit until it can verify a successful
exit. The previous lab results remain under their own failed evidence directories.

In this earlier run, the terminal was opened through Sway IPC; the later keyboard
and launcher run above supersedes that limitation. The tty1 PAM session in both
runs was started by a test-only systemd unit, not by a human entering a password
on that console. Physical monitors, real graphics hardware, accelerated rendering,
physical keyboards/mice, suspend and resource targets remain open. No release or
environment publication is implied.
