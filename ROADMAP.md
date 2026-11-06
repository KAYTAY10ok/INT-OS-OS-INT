# INT Linux roadmap

INT Linux is an independent upstream-source distribution with two editions, INT-OS and OS-INT, and one shared desktop. Yocto/OpenEmbedded remains the preferred build system. The roadmap advances through small milestones with retained evidence; documentation or a recipe alone does not complete a runtime feature.

## Phase 0 — architecture and feasibility

- [x] Inspect the existing repository and four desktop references.
- [x] Record an initial Yocto suitability comparison and technical risks.
- [x] Document an initial threat model, performance methodology, and hardware test tiers.
- [x] Verify a supported Yocto release, exact source revisions, build-host requirements, and kernel maintenance policy against upstream sources.
- [x] Select the initial userspace, package backend, filesystem, desktop/installer direction, and build/test architecture with rationale in `ARCHITECTURE.md` and `DECISIONS.md`.
- [x] Inspect host resources and fetch access; plan the small build with four jobs, rm_work, shallow Git, a verified official archive mirror, and disk stop thresholds. Actual build completion remains a Phase 1 gate.

Keep the locked decisions from the master specification. Changing the preferred build system or adopting another distribution as a parent requires the project owner's explicit decision. Routine implementation choices inside the approved architecture can proceed without another confirmation.

## Phase 1 — first bootable foundation

Deliver a minimal x86-64 foundation with a pinned manifest, an INT layer, a repeatable build command, and a serial console. The disposable `int-image-smoke` image runs assertions and powers off with root locked. The separate non-test `int-image-minimal` image has also been built and observed at its serial login prompt.

- [x] Build the smoke image's kernel and root filesystem from upstream sources through Yocto.
- [x] Boot that image under QEMU and pass all seven guest assertions: architecture, init, INT identity, glibc, filesystems, locked root, and restricted network initialization.
- [x] Retain actual build/boot logs, source versions, image checksums, and the two preceding failed network-check attempts with their diagnosis.
- [x] Preserve the first known-good kernel, root filesystem, and manifest separately from deployment outputs.
- [x] Build `int-image-minimal` separately and observe kernel startup, INT banner, and serial login prompt; confirm the manifest omits the smoke package and the serial log has no smoke output, then stop the emulator externally through QMP.
- [x] Pass 22 host-side unit tests for source/bootstrap safeguards, CPU configuration guards, and smoke-runner behavior.
- [ ] Validate configured user login and guest-initiated shutdown/recovery for the non-test image.
- [ ] Repeat the successful documented workflow in a fresh or restored work directory.

The first functional smoke boot passed on 2026-11-05 in run `qemu-smoke-20261105T165955.205012Z-6c711ae0a6d6`, which remains historical evidence. The latest smoke run is `qemu-smoke-20261105T170800.850984Z-60f2c0aae128`: seven checks passed, QEMU exited 0, and no timeout occurred. The distinct minimal-image console run `minimal-console-20261105T171144.595744Z-2c65869f558e` also passed its observations and external QMP stop. It did not attempt a password login or a guest shutdown.

The final build logs report all 3154 minimal-image tasks and all 3173 smoke-image tasks succeeded, with previously valid tasks reused. These are current-workspace build results, not evidence of a fresh-machine restoration. Both final runs retain `result.json`, `serial.log`, `known-good.json`, and tested artifact copies under `/workspace/int-linux-work/evidence/`; the copies' SHA256 values match the records.

The smoke image's restricted network check verifies a DHCP IPv4 address, link UP, a connected route, and no IPv4 default route. It does not test Internet or DNS access, and those network assertions were not repeated inside the non-test console image. These are functional virtual-machine results; no boot-time benchmark or physical-hardware qualification has been completed. Fresh/restored-workspace reproducibility and the remaining user/recovery checks stay open.

## Phase 2 — shared core

- [x] Build first-owner console enrollment, locked root and password-authenticated sudo; pass real enrollment/login and incorrect-password rejection in QEMU.
- [x] Verify default IPv4 firewall packet controls, scoped atomic reloads, missing/invalid policy network startup failure, service recovery and DHCP in the disposable core VM.
- [ ] Configure users, services, networking, logging, device handling, and the kernel security baseline.
- [ ] Establish the INT package feed, dependency policy, signing and key rotation, and update/recovery tests.
- [x] Generate an initial SPDX 3.0.1 SBOM for the smoke image.
- [ ] Complete provenance and signing verification, vulnerability triage, and release-support procedures.

## Phase 3 — shared INT Desktop

- [ ] Integrate one lightweight Wayland/tiling foundation with terminal, launcher, notifications, status bar, and keyboard navigation.
- [ ] Add original INT branding and configurable layouts informed by the supplied references.
- [ ] Measure desktop overhead before adding a dashboard or custom shell component.
- [ ] Test session startup, input, accessibility needs, display changes, suspend, and recovery.

## Phase 4 — INT-OS profiles

- [ ] Build minimal, standard, and desktop profiles from shared components.
- [ ] Establish measured resource baselines and compare proposed optimizations against them.
- [ ] Add user-controlled resource recommendations without automatically killing processes.

## Phase 5 — OS-INT profiles

- [ ] Review the license, dependencies, architecture, maintenance, resource use, and security implications of each candidate tool.
- [ ] Add modular OSINT, CSINT, and lab groups; keep optional tools outside the base image.
- [ ] Implement and verify security profiles and isolated lab defaults.
- [ ] Preserve the shared desktop and base with INT-OS.

## Phase 6 — installer and distribution infrastructure

- [ ] Create live/USB installation media and an installer using maintained disk and boot tools.
- [ ] Require explicit confirmation of destructive disk operations and test on disposable virtual disks.
- [ ] Provide account, keyboard, timezone, encryption, bootloader, logs, and recovery workflows.
- [ ] Publish signed INT feeds and verified release images through a documented release process.

## Phase 7 — release qualification

- [ ] Pass functional, security, update, recovery, installation, and desktop checks on release artifacts.
- [ ] Benchmark exact low-end, mid-range, and workstation reference hardware.
- [ ] Review license obligations, known issues, compatibility claims, and support scope.
- [ ] Complete independent review and retain release candidates and evidence.

## Evidence and status updates

Update [requirements](docs/development/requirements.md) and `CLAUDE_HANDOFF.md` after each milestone. Record the tested artifact and revision, commands, actual outcomes, and remaining work. A failed build stays a failed build until the affected command is corrected and rerun; skipped or unavailable hardware checks stay open.
