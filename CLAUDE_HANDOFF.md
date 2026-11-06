# Independent audit handoff

Current work: shared desktop integration after the verified console core, not a complete operating-system
release. INT-OS and OS-INT retain one shared architecture. No dependency on Claude
Code is required to build or test it.

## Desktop prototype — headless VM verified, 2026-11-06

The new `meta-int-desktop` layer and source pin for meta-wayland
`2b97daa23e0e612a087ea54b150bd0b8e0ff9378` implement stable Sway 1.11 /
wlroots 0.19.3, foot/fuzzel/swaybar and original shared configuration. The separate
`--profile desktop` helper configuration uses `build-desktop`, common caches,
and ABI `6.18.54-int-desktop1`/`r2`. The default core configuration is preserved.
Effective desktop source/CPU/feature/ABI checks and image build pass. Inspect
`../int-linux-work/check-desktop-resumed.log` and `build-desktop-smoke-4.log`.

The real VM now passes rootless headless Sway, IPC, Wayland, terminal mapping,
session exit and the inherited core checks. See
[validation-desktop-2026-11-06.md](docs/development/validation-desktop-2026-11-06.md)
and `../int-linux-work/evidence/qemu-smoke-20261106T102535.306207Z-e7d97f992755/`.
DRM seat/input and graphical output need a later test. `BUILDING.md` gives the
profile commands; the earlier completed core milestone follows.

## Current verified milestone — shared console core, 2026-11-05

Both `int-image-core` and `int-image-core-smoke` build. The smoke variant completes
real first-owner enrollment, non-root login, wrong-password rejection and successful
sudo, real isolated TCP firewall controls, failure/recovery of network startup,
DHCP and clean poweroff. The final host suite passes 57 tests. Source/configuration,
kernel ABI/module and production test-package separation audits pass.

Read [validation-core-2026-11-05.md](docs/development/validation-core-2026-11-05.md)
for exact scope, artifacts and failures. Full VM PASS:
`qemu-smoke-20261105T212147.613206Z-638aa279a483`. Source/log/SBOM/production-artifact
bundle: `../int-linux-work/evidence/shared-core-20261105T212416Z/`.
The new ABI is `6.18.54-int-core1`; conntrack/nft-ct are module packages in both
core variants, veth in the test variant. Do not pair the old foundation rootfs
with the current deploy/bzImage alias. The runner now rejects different ABI names.

The full interactive test used the smoke variant; production was built and
archive-audited. No physical machine, desktop, signed feed or release is qualified.
No publication or push occurred. Next: signed-feed/OpenPGP backend qualification
and the shared desktop, following the two integration plans in docs/development.

## Earlier verified milestone — foundation, 2026-11-05

Both `int-image-minimal` and `int-image-smoke` build successfully. The final smoke
image passes all seven guest assertions on QEMU TCG/qemu64 and powers off; the
separate non-test image reaches its INT login prompt and is stopped externally
through QMP. The host suite passes 22 tests. Effective CPU/source checks pass,
and all 16 static kernel configuration checks pass. Physical hardware and
performance have not been qualified.

See [validation-2026-11-05.md](docs/development/validation-2026-11-05.md) for exact
commands, scope, failures, artifact hashes and local evidence locations. The
latest full PASS is `qemu-smoke-20261105T170800.850984Z-60f2c0aae128`; the separate
minimal console boot is `minimal-console-20261105T171144.595744Z-2c65869f558e`.
Both preserve the exact tested inputs. No release or environment publication was
performed. The historical observations below must not replace this current state.

## Sources and layout

Yocto 6.0 Wrynose-compatible OE-Core and BitBake commits, kernel 6.18.54 machine
and metadata revisions are pinned in `configs/sources.lock.json` and the INT layer.
`meta-int` defines the distro, kernel fragment and minimal/test images.
`scripts/int` provides bootstrap, builder, configure, parse, build and smoke
commands. Read `BUILDING.md`, `ARCHITECTURE.md` and `DECISIONS.md` first.

## Actual validation, 2026-11-04

- GitHub origin read and authoritative Yocto documentation access succeed.
- The pinned upstream sources were fetched and verified by commit.
- The non-root Ubuntu 24.04 builder image was built successfully with TLS and
  APT signature verification. The initial CA mount permission failure was fixed
  by making the public build-time certificate mount readable by APT.
- BitBake parsed 952 recipes with zero errors. It warned about the default
  hash-equivalence database location with a shared sstate directory.
- All 18 tooling tests pass: bootstrap failure/retry and preservation of local
  changes, plus rejection of false smoke passes and process-cleanup checks.
- The first build failed on an invalid `systemd-resolved` package dependency;
  this snapshot includes resolved in the main systemd package. The dependency
  was corrected. A later build was stopped to prefer the verified official
  archive mirror and shallow Git fetches while retaining completed work.
  Native QEMU was then scoped to x86-64 and serial-only operation before its
  compilation; no target security protections were removed.
- At that initial checkpoint the image was still building; boot had not run.

## Recovery check, 2026-11-05

The environment and workspace were restored with source edits, downloads and
sstate intact. The prior build had failed linking CMake and GCC. Inspection found
eight empty object files left by the earlier build interruptions, four in each
recipe; their missing symbols matched the linker errors. All other 2,288 nonempty
objects in those build directories passed an ELF-header/section integrity check.
The eight empty outputs and their two invalid archives were removed, with logs,
hashes and the repair recorded under
`../int-linux-work/evidence/compile-failure-20261105-b6971641/`.
The resumed build in `../int-linux-work/build-smoke-5.log` subsequently completed
all tasks successfully. Final rebuilt images and boot results are recorded above.
The resumed CMake and GCC compile tasks both succeeded. The final kernel
configuration was captured after `do_configure` and `do_kernel_configcheck`
succeeded: all 16 audited boot/config symbols are enabled, including the five
INT requests. The copy and report are in
`../int-linux-work/evidence/kernel-config-audit-20261105/`. This is a compile-time
configuration result, not a runtime security or performance measurement.

## Remaining limitations and audit tasks

The first two QEMU runs booted successfully through six guest assertions but
failed the network assertion. The test had incorrectly required a default IPv4
route despite QEMU `restrict=on`. The diagnostic run confirmed a DHCP lease,
active virtio-net link and connected subnet; libslirp deliberately omits DHCP
gateway/DNS in this mode. The guest check now verifies those properties and the
absence of an IPv4 default route, preserving isolation. The corrected image has
now passed twice. Diagnostic run:
`../int-linux-work/evidence/qemu-smoke-20261105T165527.701300Z-48fe3d2b6b36/`.
That foundation kernel also reported unavailable nftables netlink support for
IPMasquerade/NFTSet. The later core ABI adds the tested firewall described above;
masquerading and full network-isolation profiles remain unqualified.

The initial post-Kconfig, CPU-baseline, root-lock, test-package separation and
runner rejection checks now have evidence. Repeat affected checks after changes.
Compare the pinned 6.18.54 kernel with current upstream fixes before any release.

Signed repositories, updates/rollback, encryption, secure boot, AppArmor policies,
installer, desktop, hardware testing and benchmarks remain unimplemented. Review
the entire package/software supply chain and test rejection paths before release.
The full checklist is `docs/development/requirements.md`.

`docs/security/tool-integration.md` records the initial 14-tool license and
dependency review. Check its Nmap/Volatility redistribution conditions, YARA
maintenance status, Amass toolchain gap and Ghidra Java requirement. This is
documentary evidence only; architecture, memory and runtime checks remain open.

User/account enrollment and the tested IPv4 firewall/network recovery subset are
now implemented and verified above. Full service/profile qualification and a small
signed INT feed with update rejection/recovery remain open. Keep desktop and
OS-INT profiles modular on the same base.
