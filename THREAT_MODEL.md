# INT Linux threat model

Status: initial design for INT-OS and OS-INT. This document describes required controls and their validation; it does not assert that they are implemented. The first milestone is a development image for a local QEMU guest.

## Assets and trust boundaries

| Asset | Relevant boundary | Main concern |
| --- | --- | --- |
| Source manifests, recipes, and build outputs | Upstream source → build worker → release artifact | A substituted source or compromised worker can affect every installed system |
| Package and release signing keys | Build worker → separate signing authority | A stolen key can authorize malicious updates |
| Personal files and research evidence | User session → privileged services and applications | Unauthorized access, corruption, disclosure, or loss of provenance |
| Passwords and application credentials | User session → application and remote service | Credential disclosure through files, logs, or hostile content |
| Host and local network | Research guest → lab network → operator workstation | A lab workload can reach unintended systems or escape its intended boundary |
| Boot and recovery state | Firmware → bootloader → kernel → root filesystem | Unverified boot components or a broken update can defeat later controls |

The operator controls the local build and explicitly authorizes any security assessment. Network transport is treated as untrusted even when it uses an authenticated proxy. TLS, source checksums, source revision pins, and package verification serve different purposes and must remain enabled.

## Adversaries and planned controls

| Threat | Planned control | Evidence required before claiming protection |
| --- | --- | --- |
| Tampered or malicious upstream source | Exact source pins, upstream checksums/signatures, dependency review, SBOM and provenance | Fetch verification failure tests, source inventory, and an inspectable build record |
| Compromised package mirror | Signed packages and repository metadata; reject unknown keys and stale/untrusted metadata | Valid update succeeds; tampered package, metadata, and unknown key are rejected |
| Remote attack against a default service | Minimal enabled services, firewall policy, service sandboxing, least privilege | Service inventory, listening-socket check, and policy tests from an isolated network |
| Hostile document or network capture | Unprivileged analysis, restrictive file access, disposable analysis environments | Permission and isolation tests using benign fixtures |
| Unprivileged local process | Kernel memory protections, secure file modes, separate users, MAC where supported | Configuration audit and access-denial tests |
| Lost or stolen storage | Optional LUKS2 encryption, encrypted research storage, recovery-key guidance | Install and recovery tests on disposable disks; no secret material in logs |
| Lab workload reaching the operator network | Disposable VMs, explicit interfaces and routing, controlled egress, no automatic host sharing | Reachability tests to allowed and forbidden destinations; inspect mounted shares |
| Destructive installer or failed update | Explicit disk confirmation, known-good image retention, recoverable update procedure | Disposable-disk installation and interrupted-update recovery tests |

Signing credentials must stay outside source control, images, caches, and ordinary build logs. Development keys must be visibly distinct from release keys. No release should be signed until the signing and rotation procedure is documented and tested.

## Profile contract

The profile names below come from the project specification. They are design targets, not currently enforced policies.

| Profile | Intended behavior | Required limitation to document |
| --- | --- | --- |
| NORMAL | Usable secure defaults with minimal services and verified updates | It does not isolate every desktop application |
| PRIVATE | Explicit privacy and network restrictions | VPN, proxy, DNS, and browser behavior can still disclose identity |
| RESEARCH | Unprivileged research workflow and controlled handling of evidence | Opening hostile content remains risky |
| LAB | Disposable isolated analysis and authorized assessment environments | Hypervisor flaws, shared folders, and operator mistakes can cross boundaries |
| LOCKDOWN | Restrictive access and network policy | Restrictions can break hardware, updates, and normal applications |

Each implemented profile must publish exact service, firewall, DNS, IPv6, storage, and application changes, along with tests and a rollback path. A profile must not silently weaken TLS, package verification, kernel protections, or authentication.

## Development image boundary

A development image may provide serial-console access for automated QEMU tests. Any test-only login or relaxed authentication must be explicitly labeled, limited to that image, and excluded from release configuration. Tests must not expose the guest console or management services to external interfaces. A passing QEMU boot test is not a security audit.

## Residual risks and exclusions

Firmware compromise, physical attacks while an encrypted system is unlocked, unknown kernel/hypervisor vulnerabilities, hardware side channels, malicious upstream maintainers, and operator error remain risks. No privacy profile guarantees anonymity or perfect OPSEC. Hardware testing, independent review, and ongoing vulnerability response are needed beyond the first image.

Active assessments must target owned or explicitly authorized systems. Malware analysis belongs in isolated disposable labs. INT does not authorize credential theft, covert access, unauthorized persistence or surveillance, destructive exploitation, or evasion of security controls.

## Validation status

- [x] Initial assets, adversaries, boundaries, assumptions, and residual risks documented.
- [ ] Release authentication and service inventory audited.
- [ ] Package/repository signing and rejection tests passed.
- [ ] Firewall, DNS, IPv6, lab isolation, and profile rollback tested.
- [ ] Encryption, verified boot, installer confirmation, and update recovery tested.
- [ ] Independent security review completed.
