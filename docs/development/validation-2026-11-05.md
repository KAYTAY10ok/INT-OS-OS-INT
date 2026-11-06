# Foundation validation — 2026-11-05

The first INT Linux console foundation is built from source and booted in QEMU.
This record distinguishes the instrumented guest assertions from a separate
boot of the non-test image. Neither run qualifies physical hardware, desktop,
installer, update safety, anonymity or performance.

## Sources and effective configuration

Yocto 6.0 Wrynose LTS-compatible OE-Core and BitBake commits are locked in
`configs/sources.lock.json`. The effective checks confirm `DISTRO=int-linux`,
`MACHINE=qemux86-64`, `DEFAULTTUNE=x86-64`, `TUNE_FEATURES=m64`, glibc, systemd,
RPM package generation, and the exact kernel machine/cache revisions. Compiler
stack protection, FORTIFY and format-security flags remain enabled.

The final Linux 6.18.54 configuration passed 16 static checks after Kconfig
resolution. The five INT fragment settings are enabled, along with the boot
drivers. This establishes compiled configuration, not runtime exploit resistance.

## Results

| Check | Actual outcome |
| --- | --- |
| Host tooling | 22 unit tests passed, including false-PASS rejection, process cleanup, source preservation and CPU guard regression cases |
| Metadata/effective configuration | Successful parse and no configuration-check failures |
| Minimal image build | 3,154 tasks considered, 3,130 reused; all succeeded |
| Final smoke image build | 3,173 tasks considered, 3,137 reused; all succeeded |
| Smoke guest | All seven assertions passed; QEMU exit 0, no timeout, guest powered off |
| Separate minimal guest | Kernel, INT banner and login prompt observed; no test package/output; QMP stopped the VM with exit 0 |
| Setup repeatability | Exact bootstrap/builder/configure/check install script reran successfully in this instance |
| Fresh-task restoration / GitHub Actions execution | Not run |
| Physical hardware / performance benchmarks | Not run |

The minimal console check does not authenticate a user or test guest-initiated
shutdown. Root is locked by default and an interactive account must be provisioned
through private configuration. The smoke guest checks architecture, PID 1,
INT identity, glibc, filesystems, root lock and the restricted virtual network.

QEMU uses TCG, a generic `qemu64` CPU, 512 MiB RAM and two virtual CPUs. These are
test settings, not supported hardware minima. Runtime totals include copying,
emulator startup and shutdown; they are not boot-time benchmarks.

## Retained evidence

By default `INT_WORKDIR` is `../int-linux-work`. Evidence is local, outside Git;
it has not been published or validated in a new task.

- `evidence/foundation-20261105/`: source/layer hashes, package manifests,
  SPDX 3.0.1 JSON-LD SBOMs, build logs, effective configuration and test log.
- `evidence/kernel-config-audit-20261105/`: exact final kernel configuration,
  SHA256, static audit and successful task events.
- `evidence/qemu-smoke-20261105T170800.850984Z-60f2c0aae128/`: final seven-assertion
  PASS, serial log, process status and exact booted kernel/rootfs/manifest copies.
- `evidence/minimal-console-20261105T171144.595744Z-2c65869f558e/`: separate
  non-test image console boot, retained checker, command and artifact copies.
- `evidence/qemu-smoke-20261105T165955.205012Z-6c711ae0a6d6/`: earlier full PASS,
  preserved independently rather than replaced by the later candidate.

Known-good directories retain the tested copies and their SHA256 values.

| Artifact | Packages | ext4 logical bytes | Compressed tar bytes |
| --- | ---: | ---: | ---: |
| `int-image-minimal` | 107 | 156,378,112 | 40,780,192 |
| `int-image-smoke` | 109 | 156,846,080 | 40,900,692 |

These are storage metrics, not RAM or performance measurements. No SSH server,
DNF/RPM client or named OS-INT tool is installed in these images. OpenSSL's
libcrypto/configuration dependencies do not constitute a tested OpenSSL CLI.

## Failures investigated

An invalid `systemd-resolved` dependency was corrected: this OE snapshot includes
resolved in the main systemd package. Interrupted builds then left eight empty
CMake/GCC objects and two invalid archives. Those confirmed damaged outputs were
removed; all other 2,288 nonempty objects passed an ELF integrity check. The
resumed compilations succeeded without changing upstream sources or checksums.

The first two QEMU runs failed the network assertion. The test demanded a default
IPv4 route while libslirp `restrict=on` deliberately omits DHCP gateway/DNS.
Diagnostics proved a dynamic DHCP address, active link and connected route.
The corrected test verifies those properties and absence of an IPv4 default
route, keeping the restricted backend and sending no external probe. Both failed
records remain failed. DNS, Internet access and IPv6 leak behavior are untested.

An effective-configuration guard also initially rejected ordinary hardening flags
as CPU tuning. Its machine-flag filter was corrected and regression-tested to
accept hardening while continuing to reject AVX and narrow/native architecture
requirements. No protection was disabled to obtain a pass.

## Release limitations

The pinned kernel needs upstream security-update review before release. Networkd
reports unsupported nftables netlink functions for IPMasquerade/NFTSet. A guest
firewall, MAC policy, encryption, verified boot, signed feeds, update/rollback,
installer, desktop, security-tool profiles and hardware qualification remain open.
