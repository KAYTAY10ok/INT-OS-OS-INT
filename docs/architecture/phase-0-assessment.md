# INT Linux — Phase 0 initial assessment

**Status:** historical initial assessment; current selections and verification are in [ARCHITECTURE.md](../../ARCHITECTURE.md) and [CLAUDE_HANDOFF.md](../../CLAUDE_HANDOFF.md).

**Assessment date:** 2026-11-04

**Repository inspected:** `KAYTAY10ok/INT-OS-OS-INT`, local commit `76cb5c0ba72c8dc4d4b372fb223800291fe0f47c`.

This document records an initial architecture recommendation from the project specification and the files currently in the checkout. It is not evidence that any INT component has been implemented or built. The project should keep Yocto/OpenEmbedded as its preferred path while the proposed choices below are validated against current upstream documentation and a small prototype.

**Resumed-work note, 2026-11-04:** GitHub and official Yocto access now work.
Wrynose 6.0 LTS, exact OE-Core/BitBake commits and the 6.18.54 kernel snapshot
are pinned. The non-root builder succeeds and 952 recipes parse without errors.
The first image build is underway. Earlier proxy/tool observations below describe
the initial inspection only; the authoritative current result is in the handoff.
Routine selections inside the locked architecture do not require another
confirmation; the owner has authorized continuing the first prototype.

## Repository and build environment

The checkout contains a short README and four desktop reference images. There are no Yocto layers, build configuration, source manifests, package recipes, scripts, or tests yet. The working tree was clean before this document was added. No submodules were reported.

The cloud host is Debian 13 on x86_64, with 5 visible CPUs, about 33 GiB RAM, and about 60 GiB free in the workspace filesystem. `bitbake`, `kas`, and `qemu-system-x86_64` are not installed. APT has no package indexes in this instance. A read-only `git ls-remote` to the configured GitHub origin failed because the configured HTTP proxy refused the connection on port 8080. The failure occurred before Git authentication; it does not establish a missing credential. The environment status currently reports the network policy as enforced, and GitHub is in its allowed destinations.

This host is adequate for architecture work and likely useful for a small image proof once network access is restored. Five CPUs and 60 GiB of storage are constrained for repeated Yocto builds. Keep downloads and build output outside the repository, reuse sstate, begin with a single x86-64 target, and confirm free disk requirements before building. A full desktop build should wait until storage capacity and fetch access are known.

## Architecture recommendations

### 1. Yocto/OpenEmbedded suitability

Yocto is a strong match for producing controlled, reproducible base images from upstream source and maintaining separate INT layers. BitBake recipes, machine and distribution configuration, SDK generation, package feeds, and shared-state caching support the first bootable milestone well.

The main cost is ongoing recipe and layer maintenance. A general desktop needs a broad set of applications, frequent security updates, graphics and firmware integration, and a reliable package feed for software installed after the image ships. Yocto can produce those pieces, but it does not remove that maintenance burden or provide a ready-made desktop application catalog. It is a better fit for the curated INT base than for promising a large, fast-moving catalog on day one.

Keep Yocto as the preferred build system and validate it with a deliberately narrow prototype: a minimal x86-64 image, one desktop package group later, an SDK, and an RPM feed. Track how much recipe work is needed for the selected desktop and representative OS-INT tools before committing to a broad catalog.

| Approach | Fit for INT | Main maintenance cost |
| --- | --- | --- |
| Yocto/OpenEmbedded | Best initial fit for reproducible, customized images and split INT layers | Recipe and layer upkeep, release migration, security fixes, and a curated application catalog |
| Custom source build system | Maximum control, but no mature build graph or package metadata comes for free | Must create and maintain build ordering, dependency resolution, signing, feeds, SDKs, reproducibility, and update policy |
| Buildroot | Useful for small appliances and recovery images | Its package and root-filesystem model is a poor fit for a frequently updated general desktop |
| Nix-based packaging | Useful technology to evaluate for reproducible development tools | A NixOS base would conflict with the no-parent-distribution decision; combining Nix with Yocto adds two package models |

Do not switch the approved preference based on this desk assessment. Revisit it only if the desktop and package-feed prototype produces concrete evidence that the maintenance model is unsuitable.

### 2. Kernel

Use the 6.18.y Linux LTS line as the provisional starting point, with a conservative x86-64 baseline and no AVX/AVX2 requirement. Before pinning it, verify its current long-term support status, security-maintenance window, Yocto recipe availability, and driver compatibility against upstream sources. Pin the exact source revision in the layer and define a regular update and CVE review cadence. The host's `6.18.57` kernel is an environment fact, not proof that this is the correct INT kernel.

Start with upstream configuration and a small, reviewable INT fragment. Measure changes against that baseline; retain kernel hardening unless a demonstrated compatibility issue requires a documented exception.

### 3. Userspace, init, and services

Start with glibc for broad desktop and security-tool compatibility, systemd for init, service supervision, device management, and service sandboxing, and NetworkManager for laptop and desktop connectivity. Use upstream coreutils, util-linux, Bash, and journald. Keep the installed service set small and use systemd unit hardening where the service supports it. Evaluate AppArmor as the first mandatory-access-control candidate after confirming its Yocto integration and policy coverage.

These are recommendations, not approved final selections. Record exact versions and configuration once validated.

### 4. Package backend

Prototype RPM packages with DNF and signed repository metadata. RPM/DNF offers mature dependency resolution and a familiar desktop package workflow while Yocto can generate the packages and feeds. Keep the initial repository curated and modular; do not promise every upstream application.

Compare this prototype with IPK on package size and operational complexity. IPK may reduce footprint, but RPM/DNF is the stronger initial fit for dependency inspection and an INT-managed desktop feed. Treat image-level updates and rollback as a separate design decision; do not mix an untested transactional updater into the first bootable milestone.

### 5. Shared desktop and editions

Use one Wayland desktop foundation for both editions. Prototype Sway as the tiling compositor, with a small status bar, terminal, launcher, and notification service from maintained upstream projects. Keep the first theme and layout in configuration. Build an INT dashboard only after measuring the cost and identifying behavior that upstream components cannot provide.

The reference images point to dark terminal workspaces, thin blue/cyan accents, compact system information, ASCII branding, and tiled panes. One reference includes third-party character artwork; use the layout and color direction as inspiration and create original INT branding and artwork.

INT-OS and OS-INT should share the same base image, compositor, theme, and settings. INT-OS selects lightweight terminal, desktop, and productivity package groups. OS-INT adds opt-in OSINT, defensive CSINT, and isolated lab groups. Keep active scanning tools out of the default base and document that they are for owned or explicitly authorized systems.

### 6. Security model

Protect user files, investigation notes and evidence, signing keys, package integrity, and system availability. Relevant adversaries include a network attacker, a malicious or compromised package, a hostile input file, an unprivileged local account, and a compromised upstream build dependency. Trust boundaries include firmware and boot, root versus user processes, signed repositories, network-facing applications, and isolated lab workloads.

The baseline should include least privilege, verified and signed packages and images, no telemetry by default, full-disk encryption as an installation option, a default-deny host firewall policy that remains usable, and service/process isolation. Use established cryptography. Run malware analysis and offensive security tools in disposable VMs or similarly isolated labs, with explicit network controls.

Residual risks include firmware compromise, kernel vulnerabilities, hardware side channels, mistakes by an authorized operator, application data escaping a lab, and third-party supply-chain compromise. A VPN or Tor integration cannot guarantee anonymity. Define measurable controls and limitations per profile instead of claiming perfect OPSEC.

### 7. Installer and disk layout

For the first release, evaluate Calamares as the installer UI and verify that its modules can install the Yocto-generated image and configure INT's boot and package settings. Keep partitioning and bootloader behavior in small, testable modules. If integration proves too costly, use a thin INT frontend over established partitioning and encryption tools rather than implementing disk operations from scratch.

Offer UEFI first, ext4 as the simple default, and LUKS2 full-disk encryption as an explicit option. Evaluate Btrfs snapshots for recovery separately. Show the target disk and destructive changes plainly and require a final explicit confirmation before formatting. Keep unattended installation separate from the interactive path and write an installation log that avoids secrets.

### 8. Performance and compatibility plan

Set budgets after measuring a reproducible baseline. For each image profile, record exact hardware, firmware, kernel, image revision, and test procedure. Measure idle and peak RAM, idle CPU, firmware-to-login and desktop startup time, application launch, storage I/O, network overhead, compositor cost, and service consumption. Use the same workloads and warm/cold-cache rules across runs; report distributions rather than a single favorable sample.

Use three benchmark classes, not as published minimum requirements: a low-end x86-64 machine with limited cores and memory, an ordinary modern laptop or desktop, and a workstation. Add a QEMU x86-64 run for boot and regression checks, but do not treat virtualized performance as hardware compatibility evidence. Track temperature and power only where the hardware exposes reliable sensors.

| Class | Initial test profile | Purpose |
| --- | --- | --- |
| Low-end | Older x86-64 CPU, few cores, limited RAM and storage | Find boot, memory-pressure, and background-service costs |
| Mid-range | Current mainstream laptop or desktop with integrated graphics | Represent the primary desktop experience |
| High-end | Recent workstation with more cores, RAM, and dedicated graphics | Exercise parallel security workloads and graphics drivers |

These profiles define test coverage, not minimum hardware requirements. Choose exact machines and publish their specifications before accepting performance targets.

### 9. Main technical risks

- **Recipe and update load:** a growing desktop and security catalog can outpace a small team's ability to patch, rebuild, sign, and test packages.
- **Build capacity:** this instance has only 60 GiB free and five CPUs; desktop builds and retained caches may exceed its practical capacity.
- **Supply-chain reachability:** Yocto recipes fetch from many upstream hosts. The current proxy failure prevents checking source access or package signatures.
- **Package consistency:** mutable DNF updates must remain compatible with the image and its kernel; image and package release policies need an explicit boundary.
- **Desktop integration:** Wayland, graphics drivers, firmware, accessibility, and suspend behavior require hardware testing beyond QEMU.
- **Isolation assumptions:** security tools can expose host data or networks if lab boundaries and defaults are weak.
- **Installer data loss:** partitioning errors are destructive, so target review, confirmation, logs, and recovery tests are release blockers.

### 10. Roadmap and first bootable milestone

1. Restore outbound proxy connectivity and confirm that GitHub read access works. Inventory required Yocto fetch hosts from the pinned release and selected layers before requesting any allowlist additions.
2. Validate the current Yocto release, native Debian 13 prerequisites, the 6.18 LTS choice, package feed support, and Sway integration from upstream documentation.
3. Create a pinned build manifest and the smallest `meta-int` layer. Build a `qemux86-64` minimal image with serial console and a basic login; boot it in QEMU and verify kernel, root filesystem, init, serial output, and basic networking.
4. Add the shared desktop package group and compare image size and idle resource use with the minimal baseline.
5. Prototype RPM/DNF feed signing, update and rollback behavior, then add INT-OS and OS-INT package groups.
6. Add installer and security profiles after the image and package model are stable; test install, update, recovery, and security boundaries before release images.

The first bootable milestone is only the minimal serial-console QEMU image. It does not include a desktop, installer, package repository, or security-tool suite.

## Decisions for project-owner review

The locked project decisions remain unchanged. Before Phase 0 is closed, review these concrete selections: 6.18.y as the initial kernel line after lifecycle verification; glibc and systemd; RPM/DNF as the package/feed backend; Sway as the shared desktop prototype; Calamares versus a thin INT installer; and whether the cloud build environment should receive more storage for desktop builds.

## Current blockers and verification status

- **Verified locally:** repository identity and commit, clean checkout before this document, Debian 13 x86-64 host, CPU/memory/workspace capacity, absence of BitBake/Kas/QEMU, four visual references, and no submodules.
- **Failed:** the read-only GitHub fetch check could not connect to the configured proxy at `proxy:8080`.
- **Not run:** dependency installation, BitBake build, QEMU boot, tests, kernel lifecycle verification, and external Yocto/package-backend research.
- **Next required action:** restore the environment's proxy service, then rerun the GitHub read check and install the pinned build prerequisites. Do not claim Phase 0 complete until the upstream checks and first-image resource plan are verified.
