# Technical decisions

The master specification's locked decisions remain in force. Ordinary prototype
choices below proceed within them. A different parent distribution, a switch
away from Yocto, separate desktops, or destructive operations require explicit
owner authorization. No cloud environment publication is performed by this work.

| Decision | State | Reason / revisit trigger |
| --- | --- | --- |
| Standalone OE-Core + BitBake | Selected for first build | Avoid a reference distro layer; keep one small INT layer |
| Wrynose 6.0 LTS | Sources pinned | Support through 2030; review maintenance updates before release |
| 6.18.54 OE kernel snapshot | Prototype pin | Coherent with metadata; upstream patch gap is a release blocker |
| Generic x86-64 | Selected | Honor broad CPU compatibility and no mandatory AVX |
| glibc + systemd | Selected | Compatibility, maintained device/service integration |
| RPM generation / DNF feed | Prototype architecture | Mature dependency model; feed signing and rollback unimplemented |
| ext4 | QEMU foundation | Simple initial root filesystem; encryption/snapshots later |
| Sway + Wayland | Planned prototype | Shared tiling desktop, no custom compositor |
| AppArmor | Planned evaluation | Requires policy coverage and positive/negative enforcement tests |
| Calamares | Planned evaluation | Reuse installer components if Yocto integration is practical |

Yocto offers a mature dependency graph, source checksums, SDK generation, caching,
packaging, licensing and image production. The cost for a general desktop is
recipe maintenance, broad application coverage, branch migrations and security
updates. Validate representative desktop and security tools before expanding the
catalog. A custom source build system recreates much of that machinery; Buildroot
does not provide the desired mutable desktop package workflow. A Nix-based model
adds a second package architecture and is not selected. See the initial comparison
in `docs/architecture/phase-0-assessment.md`.
