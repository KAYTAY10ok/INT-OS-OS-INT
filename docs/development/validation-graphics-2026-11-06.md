# Graphical console prototype validation — 2026-11-06 UTC

The shared desktop now passes a graphical QEMU test using a local tty1 session,
PAM/logind and the emulated Virtio VGA device. This is a virtual-machine
milestone, not a physical-hardware, input-device or performance qualification.

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

The terminal was opened through Sway IPC, not by a keyboard event. The tty1 PAM
session was started by a test-only systemd unit, not by a human entering a password
on that console. Physical monitors, real graphics hardware, accelerated rendering,
keyboard/mouse interaction, launcher selection, suspend and resource targets
remain open. No release or environment publication is implied.
