# INT Linux hardware compatibility

Status: the smoke image has passed functional QEMU assertions, and the separate minimal image has reached its serial login prompt; physical coverage remains planned. No physical machine is certified or supported by test evidence yet. x86-64 is the primary architecture; an x86-64 baseline must not require AVX or AVX2. Use runtime feature detection for optional acceleration.

## Coverage tiers

| Tier | Intended coverage | Evidence needed |
| --- | --- | --- |
| Virtual foundation | x86-64 QEMU, serial console, virtual storage and networking | Actual boot, root mount, init, command execution, and network checks against a named image |
| Core physical system | UEFI boot, storage, input, Ethernet, basic display, shutdown and recovery | Installation and boot logs from each exact machine |
| Integrated desktop | Common integrated graphics, Wi-Fi, audio, brightness, hotplug, suspend and resume | Desktop and power-cycle tests with driver/firmware versions |
| Extended hardware | Discrete graphics, unusual controllers, docks, specialist peripherals | Vendor- and device-specific tests and documented limitations |

A successful virtual boot does not certify physical hardware. A driver present in the kernel configuration does not establish that the device works. Firmware and redistribution licenses must be checked before inclusion in an image.

## Verified virtual foundation

On 2026-11-05, the latest `int-image-smoke` run `qemu-smoke-20261105T170800.850984Z-60f2c0aae128` passed under QEMU 8.2.2 TCG with the `qemu64` CPU model, 2 virtual CPUs, and 512 MiB configured guest RAM. These are test-fixture settings, not a minimum hardware specification or a measurement of idle RAM.

All seven assertions passed: x86-64 architecture, systemd as PID 1, INT OS identity, glibc, writable temporary filesystem and basic proc/sys access, locked root, and restricted virtual-network initialization. QEMU exited 0 without timeout. The kernel, ext4 root filesystem, manifest, serial log, result, and known-good record are retained under `/workspace/int-linux-work/evidence/qemu-smoke-20261105T170800.850984Z-60f2c0aae128/`; the artifact copies match their recorded SHA256 values.

Networking verifies a dynamic DHCP IPv4 address, link UP, a connected subnet route, and absence of an IPv4 default route under QEMU's restricted user networking. It does not demonstrate DNS or external connectivity.

The separate `int-image-minimal` console run `minimal-console-20261105T171144.595744Z-2c65869f558e` used the same emulator/CPU/RAM settings. It observed kernel startup, the INT banner, and a login prompt, confirmed that the manifest omits the smoke package and the serial log has no smoke output, then stopped QEMU externally through QMP with exit 0. No password login, guest-initiated shutdown, or in-guest network assertions were attempted. Its own artifacts and result are retained under `/workspace/int-linux-work/evidence/minimal-console-20261105T171144.595744Z-2c65869f558e/`, with matching SHA256 values.

Both tests boot a kernel directly into a virtual ext4 root filesystem. They do not validate UEFI installation, Secure Boot, real storage/network adapters, or fresh-machine restoration.

## Reference classes for benchmarking

| Class | Selection goal | Current status |
| --- | --- | --- |
| Low-end | Modest x86-64 machine with limited cores, memory, and storage | Exact machine not selected; not measured |
| Mid-range | Ordinary current laptop or desktop with common integrated graphics | Exact machine not selected; not measured |
| High-end | Workstation for concurrent research workloads and dedicated graphics | Exact machine not selected; not measured |

These classes describe test coverage, not minimum RAM, CPU, or storage requirements. Select and record exact machines before setting numerical performance budgets. The cloud build host is not a target-hardware reference.

## Compatibility record

Every reported device test must identify:

- Manufacturer/model, CPU, RAM, storage controller and drive, graphics, network adapters, and relevant PCI/USB identifiers.
- Firmware/UEFI revision, boot mode and Secure Boot state.
- Image checksum, repository revision, kernel version/configuration, firmware packages, and graphics/session versions.
- Commands and workloads, passed and failed behavior, workarounds, and recovery steps.

Do not publish serial numbers, MAC addresses, user credentials, or other unnecessary personal identifiers in public records. Report Secure Boot or encryption as untested until their verification and recovery workflows have run.

## Current verification checklist

- [x] Primary architecture and conservative CPU policy recorded.
- [x] Virtual and physical coverage gates defined.
- [x] Disposable smoke image booted under QEMU with all seven assertions and retained evidence.
- [x] Non-test `int-image-minimal` image built separately and observed at its serial login prompt, with external QMP stop.
- [ ] Configured user login and guest-initiated shutdown/recovery tested for the non-test image.
- [ ] UEFI installation and recovery tested on physical hardware.
- [ ] Low-end, mid-range, and high-end reference machines selected and tested.
- [ ] Integrated graphics, Wi-Fi, audio, input, suspend, and hotplug results recorded.
- [ ] Discrete graphics and specialist hardware limitations recorded.

Supported-hardware claims may only be added beside their actual test evidence and known limitations.
