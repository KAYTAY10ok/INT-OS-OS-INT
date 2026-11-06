# Testing

The foundation has three distinct verification stages:

1. `./scripts/int check`: parse the real metadata with the pinned BitBake.
2. `./scripts/int build int-image-smoke`: compile the real kernel/root filesystem.
3. `./scripts/int smoke`: boot the resulting image in QEMU TCG, using a generic
   x86-64 CPU without AVX and no host port forwarding.

The guest must verify architecture, PID 1, INT identity, glibc, mounted and writable
filesystems, root-account lock, and DHCP/link/connected-subnet routing, then print the complete
success markers and power off. The runner rejects a missing assertion, a failure
marker, a kernel panic, an abnormal QEMU exit, or a timeout. It records exact input
hashes, serial output, command, and QEMU version in a unique evidence directory.

The VM uses libslirp `restrict=on`. That backend deliberately omits the DHCP
gateway and DNS options. The guest requires a dynamic IPv4 address, an active
link, a connected local route and no IPv4 default route. It sends no remote probe
and does not claim DNS, Internet or IPv6 leak-test coverage. The first failed
network check incorrectly expected a default route; diagnostic boot logs proved
DHCP was working. See the upstream behavior in
https://gitlab.freedesktop.org/slirp/libslirp/-/blob/v4.7.0/src/bootp.c#L278 .

Run `python3 -m unittest discover -s tests` for the smoke runner's negative cases.
These tests check rejection of false success; they do not replace the guest boot.

The shared-core image adds a separate test path:

```sh
./scripts/int build int-image-core-smoke
./scripts/int core-check
```

It enrolls a fresh console owner through real `passwd`, then verifies the owner
record, root lock and repeat enrollment. In-guest network namespaces and TCP
probes test input drop, loopback, a narrow temporary allow rule, and restoring
the drop policy. Separate checks require repeated reloads and invalid nft
transactions to preserve existing tables. Missing/invalid firewall configuration
must prevent networkd from starting; restoring it must recover services and DHCP.
The final console login must use a non-root UID. Sudo must reject an incorrect
password and then accept the correct one before the guest powers off.

The runner keeps its random test password in memory and captures only guest
output. Any credential echo fails the test; transcripts are redacted before
writing. Successful evidence preserves the original, unprovisioned kernel,
rootfs and manifest with SHA256 hashes. Changes use a temporary QEMU overlay.
Failed runs retain diagnostics but cannot produce a known-good result.

For the graphical console prototype, run:

```sh
./scripts/int --profile desktop build int-image-graphics-smoke
./scripts/int --profile desktop graphics-check
```

The additional test uses a local PAM/logind tty1 session, Virtio VGA, Sway's DRM
backend and a real owner terminal. It uses a virtual keyboard to open the terminal,
open the launcher and select an application, and retains framebuffer captures
through a private Unix QMP socket. It does not qualify physical devices or mouse
interaction. See the [graphics record](docs/development/validation-graphics-2026-11-06.md).

`scripts/check-kernel.py CONFIG --manifest IMAGE.manifest --require-veth` audits
the merged core kernel configuration and module package presence. The official
upstream netfilter fragment selects conntrack as a module even when an earlier
INT fragment requests it built in. The core image therefore installs the needed
conntrack/nft-ct packages; the test image also installs veth. A source-fragment
inspection alone cannot establish their availability. Save this audit before
`rm_work` removes the recipe working tree.

No physical-hardware, installer, update, package-signature, MAC, desktop, or
performance qualification is implied by a QEMU pass. The smoke image is not a
release image. Actual run results and remaining failures belong in
`CLAUDE_HANDOFF.md` and `docs/development/requirements.md`.

The [2026-11-05 record](docs/development/validation-2026-11-05.md) reports the first
completed builds, two full smoke passes and a separate non-test console boot.
The [shared-core record](docs/development/validation-core-2026-11-05.md) reports
the later real enrollment/login/sudo/firewall/recovery VM pass and 57 host tests.
