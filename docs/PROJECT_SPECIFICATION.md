# INT LINUX — MASTER PROJECT PROMPT
## CODEX — CHIEF ARCHITECT, LEAD DEVELOPER & SYSTEM ENGINEER
### Official project specification — Version 2.0

You are the principal architect and sole active developer of a new independent Linux distribution named INT LINUX.

Your mission is to design, build, optimize, test, document and deliver a complete operating system ecosystem with two editions:

1. INT-OS — Ultra-lightweight, performance-first Linux distribution.
2. OS-INT — Cybersecurity, OSINT and Cyber Security Intelligence Linux distribution.

You are responsible for the complete development lifecycle.

Claude Code is temporarily unavailable. Do not depend on it to complete the project. Prepare the repository so Claude can later perform independent technical and security audits.

This is a serious long-term operating system project.

Your priority is a genuinely usable, stable, responsive and maintainable operating system, not simply an attractive prototype.

==================================================
0. FINAL LOCKED PROJECT DECISIONS
==================================================

These decisions have been explicitly approved by the project owner.

DO NOT change them without explicit permission.

PROJECT NAME:
INT LINUX

EDITION 1:
INT-OS

Purpose:
Extremely lightweight, responsive and resource-efficient operating system.

EDITION 2:
OS-INT

Purpose:
Cybersecurity, OSINT, Cyber Security Intelligence, privacy, OPSEC and authorized security research.

KERNEL:
Linux kernel, customized and optimized by INT.

DISTRIBUTION FOUNDATION:
Independent distribution built from upstream sources.

PARENT DISTRIBUTION:
NONE.

Do not base INT on Debian, Ubuntu, Arch Linux, Alpine Linux, Fedora or another complete distribution.

BUILD SYSTEM:
Yocto Project / OpenEmbedded is the preferred initial build system.

You must validate its suitability for a general-purpose desktop distribution during Phase 0.

If a serious technical limitation is discovered, document the evidence and present alternatives to the project owner before changing the decision.

ARCHITECTURE:
x86_64 as the primary architecture.

No i486 compatibility requirement.

No requirement to support 1990-era computers.

PERFORMANCE:
Prioritize fluidity, responsiveness, low resource consumption and efficient multitasking on modern and modest hardware.

DESKTOP:
One shared INT Desktop for both editions.

PACKAGE ECOSYSTEM:
INT-managed repositories and package infrastructure.

Do not build an entire package manager from scratch unnecessarily. Evaluate mature packaging backends and create an INT-native user experience around the selected architecture.

PRIMARY DEVELOPER:
Codex.

FUTURE INDEPENDENT AUDITOR:
Claude Code.

==================================================
1. PRODUCT VISION
==================================================

Create a distinctive Linux distribution that combines:

- Arch Linux-inspired terminal aesthetics.
- Ubuntu-level installation simplicity.
- Excellent responsiveness.
- Low idle resource consumption.
- Modern hardware support.
- An original desktop identity.
- Strong security architecture.
- A carefully maintained package ecosystem.
- A shared foundation for two specialized editions.

INT must feel like its own operating system.

It must not look like a generic Linux distribution with a different wallpaper.

It must have its own:
- Branding.
- Desktop identity.
- Installer.
- System configuration.
- Default applications.
- Package repositories.
- Update experience.
- Performance profiles.
- Security profiles.
- Documentation.
- Release process.

Do not reinvent mature upstream technologies without a concrete benefit.

Use upstream components where they are reliable, then integrate, configure, optimize and extend them under the INT identity.

==================================================
2. DISTRIBUTION ARCHITECTURE
==================================================

Build INT directly from upstream Linux and userspace sources using a reproducible distribution build system.

Preferred build architecture:

Yocto Project / OpenEmbedded.

Investigate:
- BitBake.
- OpenEmbedded metadata.
- Custom machine configurations.
- Custom distribution configurations.
- Package generation.
- Image generation.
- SDK generation.
- Build caching.
- Dependency management.
- Reproducible builds.
- Security updates.
- Package feeds.

Create INT-specific layers.

Suggested structure:

int-linux/
  meta-int/
  meta-int-desktop/
  meta-int-security/
  meta-int-os/
  meta-os-int/
  meta-int-hardware/
  meta-int-graphics/
  meta-int-installer/
  meta-int-tests/
  configs/
  images/
  recipes/
  scripts/
  tools/
  tests/
  docs/
  releases/

Adapt this structure to Yocto best practices.

Do not copy an entire existing distribution into the repository and rename it.

Do not depend on another distribution's root filesystem or binary package repositories.

### Phase 0 build-system validation

Yocto is the preferred approach, not an excuse to ignore technical limitations.

Investigate whether Yocto is suitable for:
- A general-purpose x86_64 desktop.
- A frequently updated desktop operating system.
- Large software repositories.
- OSINT and cybersecurity tools.
- Desktop applications.
- User-installed applications.
- Security updates.
- Long-term package maintenance.

Produce a comparison of:
- Yocto/OpenEmbedded.
- A custom source-based distribution build system.
- Other technically relevant alternatives.

Explain the maintenance cost of each.

Do not change the preferred build system without presenting a technical recommendation and obtaining approval.

==================================================
3. KERNEL AND CORE SYSTEM
==================================================

Use a modern, actively maintained Linux kernel.

Prefer a suitable upstream LTS branch at the start of development.

Pin the exact kernel source revision and document the update policy.

Do not automatically use the newest kernel simply because it has the highest version number.

The selected kernel must balance:
- Performance.
- Stability.
- Security.
- Hardware compatibility.
- Driver availability.
- Long-term maintenance.

Create INT-specific kernel configurations.

Investigate:
- Scheduler configuration.
- CPU frequency scaling.
- Memory management.
- Filesystem support.
- Networking.
- Power management.
- Hardware drivers.
- Kernel security features.
- Preemption settings.
- Logging overhead.
- Unnecessary kernel modules.

Do not disable important kernel protections for small benchmark improvements.

Do not claim that a custom kernel is automatically faster.

Benchmark every meaningful configuration change.

### CPU architecture

Target general-purpose x86_64 hardware.

Use a conservative baseline compatible with a broad range of x86_64 computers.

Do not require AVX or AVX2 for the base operating system.

Use runtime CPU feature detection for optional optimizations.

Avoid unnecessarily compiling the entire system for a narrow CPU model.

Support:
- Modern desktops.
- Laptops.
- Modest x86_64 machines.
- Virtual machines.
- Common integrated graphics.
- Dedicated graphics where drivers permit.

Do not introduce arbitrary minimum RAM requirements before benchmarking.

Establish documented hardware compatibility tiers.

### Core userspace

Evaluate and select appropriate implementations for:
- C library.
- Init system.
- Service manager.
- Shell.
- Core utilities.
- Logging.
- Networking.
- Device management.
- Filesystem tools.

Prioritize compatibility and maintainability.

Consider glibc for broad application compatibility, and evaluate musl only if a measured performance or footprint advantage justifies the additional compatibility complexity.

Document every important selection.

==================================================
4. INT-OS — ULTRA-LIGHTWEIGHT EDITION
==================================================

INT-OS is the performance-first edition.

Its central philosophy:

EVERY COMPONENT MUST JUSTIFY ITS RESOURCE CONSUMPTION.

Priorities:

1. Low idle RAM consumption.
2. Minimal idle CPU consumption.
3. Fast startup.
4. Responsive desktop interaction.
5. Efficient multitasking.
6. Low background activity.
7. Minimal unnecessary dependencies.
8. Efficient storage usage.
9. Reliable hardware support.
10. Excellent usability.

### System profiles

INT-OS MINIMAL:
- Essential Linux system.
- Essential drivers.
- Terminal.
- Minimal services.
- No mandatory desktop.
- Basic networking where requested.

INT-OS STANDARD:
- Full terminal environment.
- File management.
- Basic networking.
- Lightweight graphical environment.
- Essential user applications.

INT-OS DESKTOP:
- Shared INT Desktop.
- Tiling windows.
- System dashboard.
- Custom themes.
- Productivity utilities.

### Performance principles

Use:
- Lazy service startup.
- Efficient service dependencies.
- Minimal daemons.
- Efficient memory allocation.
- Sensible caching.
- Efficient filesystem configuration.
- Configurable background services.
- Low-overhead monitoring.
- Minimal logging overhead.
- Runtime hardware optimization.

Avoid:
- Unnecessary background animations.
- Constant polling.
- Unnecessary telemetry.
- Redundant services.
- Heavy graphical effects.
- Excessive default applications.
- Unnecessary startup programs.

Do not sacrifice security or stability for artificial performance scores.

### Resource management

Build an INT Resource Manager that can:

- Monitor resource consumption.
- Identify heavy processes.
- Display memory pressure.
- Display CPU usage.
- Display storage activity.
- Identify unnecessary startup services.
- Provide safe recommendations.
- Offer user-controlled performance profiles.

Do not kill processes automatically merely because they consume resources.

The user must remain in control.

==================================================
5. OS-INT — CYBER INTELLIGENCE EDITION
==================================================

OS-INT must share the INT Foundation and INT Desktop.

It is optimized for professional cybersecurity research, intelligence gathering, defensive analysis and authorized testing.

It must not become a random collection of preinstalled hacking tools.

Build a coherent, modular cybersecurity environment.

### OSINT capabilities

Support:
- Public information research.
- Domain intelligence.
- DNS intelligence.
- IP intelligence.
- Public infrastructure mapping.
- Website analysis.
- Public metadata analysis.
- Information correlation.
- Source verification.
- Investigation management.
- Research documentation.
- Evidence organization.

### CSINT — Cyber Security Intelligence

Support:
- Threat intelligence.
- IOC management.
- Vulnerability assessment.
- Attack surface analysis.
- Network security analysis.
- Incident response.
- Threat hunting.
- Malware analysis in isolated environments.
- Security event correlation.
- Authorized penetration testing.
- Security research documentation.

### Tool integration

Evaluate the integration of:

- Nmap.
- Wireshark.
- tcpdump.
- OpenSSL.
- GnuPG.
- YARA.
- Zeek.
- Suricata.
- TheHarvester.
- Amass.
- Subfinder.
- OWASP ZAP.
- Ghidra.
- Volatility.
- Additional tools when justified.

For each integration:
- Check its license.
- Check its architecture.
- Check its dependencies.
- Check its memory requirements.
- Check its security implications.
- Check its update policy.
- Check its compatibility with INT.

Do not install everything in the base image.

Create optional tool categories and installation profiles.

### OS-INT profiles

OS-INT BASE:
Essential system, security tools and shared desktop.

OS-INT OSINT:
Public information and investigation tools.

OS-INT CSINT:
Threat intelligence and defensive security tools.

OS-INT LAB:
Isolated cybersecurity laboratory and authorized testing environment.

OS-INT FULL:
All compatible components, installed selectively.

### Controlled testing

All active security testing must be restricted to systems owned by the operator or systems they are explicitly authorized to assess.

Do not develop:
- Credential theft.
- Malware.
- Unauthorized persistence.
- Covert unauthorized access.
- Destructive exploitation.
- Unauthorized surveillance.
- Security-control evasion.

Focus on defensive research, legitimate intelligence, controlled laboratories and authorized security assessments.

==================================================
6. SECURITY AND OPSEC ARCHITECTURE
==================================================

Security must be designed into the distribution.

Never promise 100% OPSEC or perfect anonymity.

Create a documented threat model.

Identify:
- Assets.
- Attack surfaces.
- Trust boundaries.
- Adversaries.
- Security assumptions.
- Residual risks.
- Known limitations.

Implement progressively:

- Least privilege.
- Secure permissions.
- Process isolation.
- Memory protections.
- Mandatory access control where appropriate.
- Package signing.
- Verified repositories.
- Verified updates.
- Secure boot support.
- Full-disk encryption.
- Encrypted research storage.
- Firewall integration.
- Network isolation profiles.
- DNS leak testing.
- IPv6 leak testing.
- Proxy configuration.
- VPN integration.
- Optional Tor integration.
- Local audit logs.
- No telemetry by default.
- Minimal external network communication.

### Security profiles

NORMAL:
Standard secure configuration.

PRIVATE:
Restrictive privacy and network configuration.

RESEARCH:
Controlled research environment.

LAB:
Isolated authorized cybersecurity testing.

LOCKDOWN:
Maximum practical restrictions with explicit limitations.

Every profile must document its actual behavior.

Never claim that a VPN, Tor or browser configuration guarantees anonymity.

Do not create homemade cryptographic algorithms.

Use established and maintained cryptographic libraries.

### Supply-chain security

Build:
- Signed packages.
- Signed repositories.
- Verified release images.
- Software Bills of Materials (SBOMs).
- Build provenance records.
- Reproducible build checks where feasible.
- Vulnerability monitoring for dependencies.

Pin important dependencies and document update procedures.

==================================================
7. INT DESKTOP — SHARED VISUAL IDENTITY
==================================================

INT Desktop is a central part of the product.

Both editions must use the exact same desktop foundation.

Do not develop two separate desktop environments.

OS-INT may add specialized widgets and investigation interfaces, but must preserve the shared visual identity.

### Visual references

The user has provided four reference images.

Inspect them carefully when available.

The target aesthetic must be extremely faithful to their overall visual language.

Key characteristics:

- Arch Linux-inspired workstation aesthetics.
- Dark terminal-first interface.
- Deep black and navy backgrounds.
- Electric blue accents.
- Subtle violet and cyan details.
- Thin borders.
- Tiled terminal windows.
- ASCII art.
- System monitoring panels.
- Minimal top bar.
- Compact typography.
- Dense but readable system information.
- Optional transparent terminal backgrounds.
- Minimal visual clutter.

Do not turn INT into a generic desktop environment.

Do not copy third-party logos or protected artwork.

Create an original INT logo, ASCII art and visual identity.

### Desktop architecture

Evaluate established lightweight desktop technologies.

Prefer mature components for difficult low-level graphics functions.

Consider:
- Wayland.
- A lightweight Wayland compositor.
- Tiling window management.
- A custom INT shell.
- A custom INT status bar.
- A custom dashboard.
- A custom theme framework.
- A custom terminal configuration.

Do not write an entire compositor from scratch unless there is a compelling engineering reason.

Avoid unnecessarily heavy desktop frameworks.

### Default desktop composition

TOP BAR:
- Clock.
- CPU.
- RAM.
- Network.
- Battery where available.
- Workspace indicator.
- System status.

MAIN WORKSPACE:
- Multiple tiled terminals.
- Configurable splits.
- Keyboard-driven navigation.
- Optional dashboard panel.

LEFT PANEL:
- INT ASCII logo.
- Hardware information.
- System status.

LOWER PANEL:
- CPU and memory monitoring.
- Network activity.
- Storage.
- Processes.

The layout must be configurable.

### Desktop profiles

INT TERMINAL:
Terminal-first layout.

INT DASHBOARD:
System monitoring and tiled terminal layout.

INT DESKTOP:
Full lightweight desktop.

INT CYBER:
Same desktop foundation with OS-INT investigation and security panels.

### Terminal

Terminal functionality must include:

- Multiple panes.
- Split layouts.
- Keyboard navigation.
- Session management.
- Custom prompts.
- Command history.
- Syntax highlighting.
- Theme configuration.
- Optional transparency.
- Fast startup.

### Dashboard

Show:
- CPU usage.
- RAM.
- Swap.
- Storage.
- Network throughput.
- Processes.
- Uptime.
- Temperature where supported.
- Hardware details.

Use efficient event-driven monitoring or sensible polling intervals.

Do not waste resources constantly refreshing information the user cannot see.

==================================================
8. PACKAGE MANAGEMENT AND SOFTWARE REPOSITORIES
==================================================

INT must own its software distribution infrastructure.

Build:
- INT repositories.
- INT package metadata.
- Package signing.
- Package verification.
- Version management.
- Dependency management.
- Repository mirrors.
- Security update mechanisms.

Do not immediately implement an entirely new package manager.

During Phase 0 evaluate suitable package backends compatible with Yocto.

Consider:
- RPM-based packaging and DNF.
- IPK-based packaging.
- Image-based transactional updates.
- Other appropriate approaches.

Select one coherent architecture after evaluating:
- Dependency resolution.
- Update safety.
- Rollback.
- Package size.
- Repository maintenance.
- Desktop application support.
- Security.
- Ease of use.
- Resource consumption.

An INT-native command-line interface may provide a consistent user experience over a mature backend.

The user-facing tool may be named:

int-pkg

It should eventually support:

- Search.
- Install.
- Remove.
- Update.
- Upgrade.
- Package information.
- Repository management.
- Verification.
- Dependency inspection.
- Rollback where supported.

Never execute unverified installation scripts automatically.

==================================================
9. INSTALLER AND ISO DISTRIBUTION
==================================================

Installation must be as easy as Ubuntu.

Provide:
- Downloadable ISO images.
- Bootable USB support.
- Live environment.
- Hardware detection.
- Disk selection.
- Partition management.
- Filesystem selection.
- Bootloader configuration.
- User account creation.
- Keyboard configuration.
- Timezone configuration.
- Edition selection.
- Installation progress.
- Error reporting.
- Recovery options.

Disk formatting must always require explicit confirmation.

Create separate release images:

1. INT-OS Minimal.
2. INT-OS Desktop.
3. OS-INT Base.
4. OS-INT Full or modular installation image.

Do not put every optional security tool into every image.

Provide installation logs.

Support automated installations for advanced users.

==================================================
10. PERFORMANCE ENGINEERING
==================================================

Performance is a fundamental product requirement.

INT must be fluid, responsive and efficient.

Do not invent arbitrary performance percentages.

Establish actual benchmarks.

Create a documented benchmark methodology.

### Required measurements

Measure:

- Idle RAM.
- Idle CPU.
- Boot time.
- Desktop startup time.
- Application launch time.
- Memory pressure.
- CPU scheduling behavior.
- Disk I/O.
- Network overhead.
- Desktop compositor overhead.
- Background service consumption.
- Package installation overhead.

### Benchmark profiles

Test:
1. Kernel boot.
2. Minimal userspace.
3. INT-OS terminal.
4. INT-OS desktop.
5. OS-INT base.
6. OS-INT with security tools.
7. Multiple simultaneous OS-INT workloads.

### Reference hardware

Test at least three classes:

LOW-END:
Modest x86_64 machine with limited RAM and CPU resources.

MID-RANGE:
Ordinary modern laptop or desktop.

HIGH-END:
Modern workstation.

Document exact hardware and software versions.

### Performance acceptance criteria

Establish measurable targets during Phase 0.

Every optimization must be compared with a baseline.

Do not accept a performance improvement if it introduces an unacceptable security, reliability or compatibility regression.

No fake benchmarks.

No fabricated screenshots.

No claims of zero lag without actual testing.

==================================================
11. DEVELOPMENT AND TESTING
==================================================

Use:
- Version control.
- Reproducible build configuration.
- Automated build scripts.
- Automated tests.
- QEMU.
- Hardware testing where possible.
- Static analysis.
- Dependency audits.
- Kernel configuration audits.

Create tests for:
- Boot.
- Hardware detection.
- Networking.
- Filesystems.
- Package management.
- Installer.
- Updates.
- Recovery.
- Desktop.
- Resource usage.
- Security boundaries.

Preserve a known-good image.

Do not overwrite working release candidates without backups.

Every significant change must be:
1. Compiled.
2. Tested.
3. Reviewed.
4. Documented.

Never claim success without actual verification.

==================================================
12. PROJECT STRUCTURE
==================================================

Maintain a clean repository.

Suggested organization:

int-linux/
  meta-int/
  meta-int-core/
  meta-int-desktop/
  meta-int-security/
  meta-int-os/
  meta-os-int/
  meta-int-installer/
  meta-int-hardware/
  configs/
  build/
  images/
  packages/
  repositories/
  installer/
  desktop/
  branding/
  tools/
  scripts/
  tests/
  docs/
    architecture/
    decisions/
    security/
    performance/
    benchmarks/
    development/
    installation/
    releases/
  releases/

Adapt to the official Yocto and OpenEmbedded conventions.

Avoid duplicate implementations.

==================================================
13. DOCUMENTATION REQUIREMENTS
==================================================

Maintain:

README.md
ARCHITECTURE.md
ROADMAP.md
BUILDING.md
DEVELOPMENT.md
SECURITY.md
THREAT_MODEL.md
PERFORMANCE.md
BENCHMARKS.md
PACKAGE_MANAGEMENT.md
DESKTOP.md
INSTALLATION.md
HARDWARE_COMPATIBILITY.md
TESTING.md
DECISIONS.md
RELEASE_NOTES.md
CLAUDE_HANDOFF.md

Update documentation after meaningful architectural or implementation changes.

CLAUDE_HANDOFF.md must always describe the actual state of the project.

==================================================
14. DEVELOPMENT PHASES
==================================================

PHASE 0 — RESEARCH AND ARCHITECTURE

Inspect the repository and environment.

Validate Yocto/OpenEmbedded suitability.

Choose:
- Kernel LTS.
- C library.
- Init system.
- Service manager.
- Package backend.
- Filesystem.
- Desktop architecture.
- Installer strategy.
- Security framework.
- Build and testing architecture.

Define:
- Hardware tiers.
- Performance budgets.
- Release profiles.
- Security threat model.

Produce architecture documentation.

Do not begin massive implementation before this phase is complete.

PHASE 1 — BUILD FOUNDATION

Create the initial Yocto layers.

Build the smallest bootable x86_64 INT image.

Boot it in QEMU.

Verify:
- Kernel startup.
- Root filesystem.
- Init.
- Serial output.
- Basic userspace.
- Network initialization where supported.

PHASE 2 — INT CORE

Implement:
- Core system configuration.
- Services.
- Networking.
- Logging.
- Hardware management.
- Security baseline.
- Package infrastructure.

PHASE 3 — INT DESKTOP

Implement:
- Terminal.
- Tiling.
- Status bar.
- Dashboard.
- Theme engine.
- Configuration.
- Keyboard navigation.

Match the provided reference images.

PHASE 4 — INT-OS

Build:
- Minimal image.
- Standard image.
- Desktop image.

Benchmark resource consumption.

PHASE 5 — OS-INT

Build:
- OSINT environment.
- CSINT environment.
- Security profiles.
- Optional security tools.
- Isolated research environments.

PHASE 6 — INSTALLER AND REPOSITORIES

Build:
- Installer.
- Package repositories.
- Signed packages.
- Update infrastructure.
- ISO images.

PHASE 7 — TESTING AND RELEASE

Run:
- Functional tests.
- Security tests.
- Performance benchmarks.
- Installation tests.
- Hardware compatibility tests.
- Recovery tests.

Produce release candidates.

==================================================
15. STRICT RULES
==================================================

1. Never claim an unimplemented feature works.
2. Never invent benchmark results.
3. Never ignore compiler errors.
4. Never hide security limitations.
5. Never change the approved architecture without permission.
6. Never base INT on an existing distribution.
7. Never create two separate desktop environments.
8. Never install unnecessary background services.
9. Never sacrifice security for performance.
10. Never use unverified packages.
11. Never erase disks without explicit confirmation.
12. Never introduce arbitrary dependencies.
13. Never overwrite a known-good build without preserving it.
14. Never generate huge speculative codebases.
15. Prefer small, testable milestones.
16. Maintain documentation.
17. Maintain reproducible builds.
18. Maintain a clear development roadmap.
19. Ask before destructive or major architectural changes.
20. Be honest about incomplete features.

==================================================
16. CLAUDE CODE HANDOFF
==================================================

Claude Code is temporarily unavailable.

Continue independently.

Maintain CLAUDE_HANDOFF.md.

Include:
- Project architecture.
- Build instructions.
- Kernel version.
- Yocto version.
- Repository structure.
- Implemented components.
- Verified features.
- Actual test results.
- Security findings.
- Performance results.
- Known bugs.
- Remaining work.
- Recommended independent audit tasks.

==================================================
17. FIRST TASK — EXECUTE NOW
==================================================

Inspect the current repository.

Do not assume it is empty.

Inspect the available build environment.

Then present:

1. Repository state.
2. Yocto suitability analysis.
3. Recommended kernel LTS.
4. Recommended userspace architecture.
5. Recommended package backend.
6. Recommended init system.
7. Shared desktop architecture.
8. INT-OS and OS-INT differences.
9. Security threat model.
10. Installer architecture.
11. Performance benchmark plan.
12. Initial hardware compatibility tiers.
13. Development roadmap.
14. Technical risks.
15. First bootable milestone.

Identify decisions that require project-owner approval.

Once Phase 0 is complete, begin building the first minimal INT Linux image.

Do not attempt to deliver the entire operating system in one operation.

Build a genuinely working distribution step by step.

PROJECT: INT LINUX
EDITION 1: INT-OS
EDITION 2: OS-INT
KERNEL: CUSTOMIZED UPSTREAM LINUX LTS
BUILD SYSTEM: YOCTO / OPENEMBEDDED (SUBJECT TO PHASE 0 VALIDATION)
PARENT DISTRIBUTION: NONE
ARCHITECTURE: X86_64
DESKTOP: ONE SHARED INT DESKTOP
PACKAGE ECOSYSTEM: INT
LEAD DEVELOPER: CODEX
FUTURE AUDITOR: CLAUDE CODE

THIS IS THE OFFICIAL MASTER SPECIFICATION.