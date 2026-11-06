# Architecture

INT builds target packages from upstream source through OpenEmbedded-Core and
BitBake. Only OE-Core's `meta` layer and `meta-int` are loaded. No Poky distro,
foreign target root filesystem, or foreign binary package feed is used.
Ubuntu provides tools in the build container; its packages are not the INT target.

## Foundation selected for the first milestone

| Component | Choice and rationale |
| --- | --- |
| Build system | Yocto 6.0 Wrynose LTS; exact OE-Core and BitBake commits in `configs/sources.lock.json` |
| CPU | Generic x86-64 (`m64`), without mandatory AVX/AVX2; override the upstream QEMU v3 default |
| Kernel | OE-maintained Linux 6.18.54, exact machine and kernel-metadata revisions pinned |
| C library | glibc for broad desktop/tool compatibility |
| Init/device handling | systemd and udev, with explicit services |
| Console tools | BusyBox, GNU utilities/Bash pulled by the OE package graph, and iproute2; manifests record the exact installed set |
| QEMU networking | systemd-networkd with DHCP; no remote test destination |
| Packages | Generate RPMs; validate DNF and signed feeds in the core-system milestone |
| Filesystem | ext4 for the first QEMU root filesystem |
| Boot test | TCG emulation on a non-AVX CPU, locked root account, serial assertions, automatic poweroff |

Systemd-networkd serves the console prototype. NetworkManager is the planned
desktop network frontend; only one network manager should manage an interface.
There is no measured performance claim for any of these choices.

The small INT kernel fragment keeps the effective configuration available for
audit and requests stack protection, address randomization and restricted dmesg.
The fragment is not proof that each setting survived Kconfig resolution; audit
the generated configuration before marking kernel hardening complete.

## Layers and targets

`meta-int/conf/distro/int-linux.conf` defines INT's identity and shared base.
`int-image-minimal` defines the console foundation with a locked root account.
`int-image-smoke` adds a QEMU-only systemd service which checks the actual guest
and powers off. It is a test artifact, not an installation image.

Add edition and desktop layers when they contain real integration work. INT-OS
will select minimal, standard and desktop groups. OS-INT will add opt-in OSINT,
defensive CSINT and isolated-lab groups. Both reuse the same desktop package group
and configuration. Avoid empty layers that imply nonexistent functionality.

## Desktop, updates and installer direction

Use one Sway/Wayland prototype, a maintained lightweight terminal and status bar,
and original INT themes informed by the four supplied references. Measure their
cost before implementing a custom dashboard or resource manager.

RPM/DNF is the initial package architecture. A feed needs signing, metadata,
version compatibility, key rotation, update rejection and recovery tests before
it becomes a supported service. Image-level rollback is a later design gate.

Evaluate Calamares integration for the installer. Use established partitioning,
encryption and boot tools, with explicit confirmation of disk formatting.
Neither installer nor destructive disk operations are part of the first build.

## Upstream evidence and limitations

Wrynose is LTS through April 2030. Its documentation lists Debian 13 and Ubuntu
24.04 as supported build hosts. The documented `rm_work` Sato example needs about
40 GB initially and 22 GB after build, making a smaller image worth attempting
on this instance's approximately 60 GiB free disk. Four jobs and disk-space stop
thresholds limit build pressure; they are not performance targets for INT.

Sources checked on 2026-11-04:

- https://www.yoctoproject.org/development/releases/
- https://docs.yoctoproject.org/6.0/ref-manual/system-requirements.html
- https://docs.yoctoproject.org/6.0/dev-manual/disk-space.html
- https://docs.yoctoproject.org/6.0/dev-manual/packages.html
- https://www.kernel.org/releases.json

Kernel.org currently lists 6.18.60. The OE snapshot has 6.18.54; this patch gap
must be reviewed and resolved before release. Do not replace SRCREVs with a
moving branch or claim the development image has passed a vulnerability audit.
The earlier [assessment](docs/architecture/phase-0-assessment.md) records the
initial proxy failure; that failure is no longer current.

The [tool integration review](docs/security/tool-integration.md) covers the 14
named security tools using upstream sources. License conditions, Amass's Go
version, Ghidra's Java runtime and Wireshark GUI dependencies require separate
integration work. None of the tools is claimed installed or tested on INT.
