# Master specification implementation status

This checklist follows the INT Linux master project specification version 2.0. A checked item means the stated work has evidence in the repository or a recorded run. It does not imply completion of the wider phase. Recipe definitions, successful parsing, built images, boot tests, physical-hardware validation, and release qualification are separate outcomes.

## Locked project constraints

| Constraint | Implementation rule |
| --- | --- |
| INT-OS and OS-INT | Two editions built from one shared foundation |
| Independent distribution | Build upstream sources; do not reuse another distribution's target root filesystem or binary feeds |
| Yocto/OpenEmbedded | Preferred initial build system; document evidence before proposing a change |
| Linux LTS, x86-64 | Pin a maintained kernel revision; conservative CPU baseline without mandatory AVX/AVX2 |
| One INT Desktop | Share compositor, shell foundation, theme, and configuration across editions |
| INT-managed software | Reuse a mature package backend and build INT signing, feeds, updates, and support policy |
| Evidence before claims | Do not fabricate tests, benchmarks, screenshots, security guarantees, or checked requirements |

## Phase 0 — research and architecture

- [x] Inspect the repository rather than assuming it is empty.
- [x] Inspect and describe the four supplied design references.
- [x] Record an initial build-system suitability comparison and maintenance risks.
- [x] Document assets, attack surfaces, trust boundaries, residual risks, and security assumptions.
- [x] Define a performance measurement contract and initial hardware test classes.
- [x] Verify and pin Yocto/tool/kernel sources: `configs/sources.lock.json`, kernel pin include, and the upstream links in `ARCHITECTURE.md`.
- [x] Select userspace, init, package, filesystem, desktop/installer direction, security and build/test architecture with rationale in `ARCHITECTURE.md` and `DECISIONS.md`.
- [x] Inspect host resources and source access, build the non-root tool container, and document the guarded first-image procedure in `BUILDING.md`. Completing the image is a separate gate below.

Evidence: [initial assessment](../architecture/phase-0-assessment.md), [threat model](../../THREAT_MODEL.md), [performance methodology](../../PERFORMANCE.md), and [hardware coverage](../../HARDWARE_COMPATIBILITY.md). The initial assessment is historical; replace outdated environment observations with a dated verified result rather than silently treating them as current.

## Phase 1 — build foundation

- [x] Add the INT layer and exact source/build configuration; BitBake parsed 952 recipes with zero errors. Independent bit-for-bit reproducibility is not yet tested.
- [x] Add the guest assertion service and QEMU evidence runner; 22 host tooling tests pass, including rejection of partial/failing output, CPU guard regressions and preservation of local source changes.
- [x] Build the minimal and smoke upstream-source x86-64 images; all tasks succeeded.
- [x] Boot the minimal image to its console and verify the derived smoke image with seven guest assertions, including DHCP/local routing in restricted QEMU.
- [x] Preserve image checksums, source versions, logs and exact known-good artifact copies in independent evidence directories.
- [x] Exercise the documented bootstrap, builder, configure, configuration-check, build and smoke commands in the actual checkout; repeat the complete install sequence successfully.
- [ ] Independently validate restoration in a new task/machine and interactive user login; current console observation does not authenticate a user.

Evidence: [foundation validation](validation-2026-11-05.md). The minimal console
run uses an external QMP stop; guest-initiated shutdown is verified only by the
instrumented smoke run. No hardware or performance qualification is implied.

## Phase 2 — core system and supply chain

- [x] Verify the requested initial kernel fragment after final Kconfig resolution; 16 symbols pass the recorded static audit in `INT_WORKDIR/evidence/kernel-config-audit-20261105/`. Runtime security and benchmarks remain open.

- [x] Build first-owner console enrollment, locked root, protected records and password-authenticated sudo; verify real login and wrong-password rejection in QEMU.
- [x] Verify the default IPv4 nftables packet policy, scoped reloads, network startup gating for missing/invalid policy, recovery and DHCP in QEMU.
- [x] Audit the merged core kernel and actual runtime module packages; retain ABI-matched images, SPDX SBOMs and source hashes. See [core validation](validation-core-2026-11-05.md).
- [ ] Complete service curation, device/network hardware coverage, logging policy, user recovery and security profiles beyond the tested console subset.
- [ ] Document kernel hardening and measured configuration changes.
- [ ] Create INT package metadata, dependency policy, feeds, signing, and verification.
- [ ] Test valid updates plus rejection of altered/unknown-key artifacts and recovery from interrupted updates.
- [ ] Generate SBOMs and provenance, track vulnerabilities, and document source/license/update obligations.
- [ ] Implement and verify optional encryption, verified boot, MAC, and recovery behavior before claiming them.

## Phase 3 — shared INT Desktop

- [x] Build the shared Sway prototype and verify its unprivileged headless session, Wayland protocols, terminal and clean exit in QEMU. See [desktop validation](validation-desktop-2026-11-06.md).
- [ ] Integrate the same lightweight tiling desktop foundation for both editions.
- [ ] Provide original INT artwork, ASCII identity, dark theme, thin borders, and configurable layouts.
- [ ] Provide terminal panes, keyboard navigation, session behavior, history, prompt/theme configuration, and optional transparency.
- [ ] Provide status, workspace, clock, CPU/RAM/network/battery indicators where supported.
- [ ] Provide dashboard metrics with bounded or visibility-aware updates.
- [ ] Verify startup, configuration, input, display, and resource cost in a running session.

## Phase 4 — INT-OS

- [ ] Build minimal, standard, and desktop profiles.
- [ ] Measure idle memory/CPU, boot, launch time, I/O, compositor, and service cost.
- [ ] Implement resource monitoring and user-controlled recommendations/profiles without automatic process killing.
- [ ] Verify each optimization against a baseline and compatibility/security checks.

## Phase 5 — OS-INT

Initial documentary evidence: [14-tool integration review](../security/tool-integration.md).
Cross-build, runtime, memory, isolation and redistribution qualification remain
open; the review does not complete the integration criteria below.

- [ ] Add base, OSINT, CSINT, lab, and selectively installed full profiles from shared components.
- [ ] Review each candidate tool's license, dependencies, architecture, memory, maintenance, and security implications.
- [ ] Integrate investigation/evidence workflows and defensive research tools as modular categories.
- [ ] Implement NORMAL, PRIVATE, RESEARCH, LAB, and LOCKDOWN with explicit behavior and rollback.
- [ ] Test lab isolation, DNS/IPv6 policy, VPN/proxy limitations, and controlled workload boundaries.
- [ ] Restrict active assessments to owned or explicitly authorized systems.

## Phase 6 — installer, repositories, and images

- [ ] Produce bootable live/USB media and the specified minimal, desktop, base, and modular security images.
- [ ] Provide hardware detection, disk/filesystem/bootloader setup, account, keyboard, timezone, edition selection, progress, logs, and recovery.
- [ ] Require explicit final confirmation of formatting and test destructive paths on disposable disks.
- [ ] Provide an advanced unattended-install path with explicit targets and safeguards.
- [ ] Operate signed INT repositories, mirrors, verified updates, and release publication procedures.

## Phase 7 — qualification and handoff

- [ ] Run boot, networking, filesystems, package, installer, update, recovery, desktop, and security-boundary tests.
- [ ] Benchmark the seven specified workload profiles across three documented physical hardware classes.
- [ ] Preserve release candidates and report passed, failed, skipped, and unrun checks separately.
- [ ] Maintain the required architecture, build, security, performance, package, desktop, installation, testing, decision, and release documents.
- [ ] Keep `CLAUDE_HANDOFF.md` aligned with actual versions, artifacts, results, bugs, and independent audit tasks.
- [ ] Complete independent review before claiming release readiness.

## Evidence update rule

When completing an item, link the implementing file and the exact verification record. If a check fails, keep the item open and record the command, artifact, error, diagnosis, and next action. Only the checks that actually ran can change status; an unavailable dependency or missing physical machine remains an explicit limitation.
