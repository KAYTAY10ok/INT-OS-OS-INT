# Development notes — 0.1.0-dev

The first foundation adds a standalone OE-Core/BitBake lock, INT distro settings,
Linux configuration fragment, generic x86-64 build, minimal and smoke-image
recipes, a containerized builder and serial QEMU verification tooling.

Verified on 2026-11-05: both source-built images compile, the smoke guest passes
seven assertions, and the separate minimal image reaches its login prompt. The
host suite passes 22 tests. Exact copies, hashes, logs, manifests and SPDX SBOMs
are retained locally; see `docs/development/validation-2026-11-05.md`.

The subsequent shared console core builds with first-owner enrollment, locked
root, password-authenticated sudo and an nftables default firewall. Its VM passes
real login, incorrect sudo-password rejection, isolated TCP controls, invalid
policy network startup gating, recovery, DHCP and clean poweroff. The host suite
passes 57 tests. See `docs/development/validation-core-2026-11-05.md` for exact
artifacts and scope; this remains an unreleased development image.

On 2026-11-06 the shared Sway/Wayland desktop prototype built and passed its
headless VM checks with a real owner session and terminal. Physical graphics,
keyboard/mouse interaction and performance remain open. See
`docs/development/validation-desktop-2026-11-06.md`.

A subsequent Virtio VGA VM test passes the actual local PAM/logind seat, Sway
software-rendered output, a user-owned terminal and clean session exit. A screen
capture and exact test inputs are retained; physical GPU and input qualification
remain open. See `docs/development/validation-graphics-2026-11-06.md`.

No release has been published. There are no supported ISOs, signed feeds,
installer, desktop, validated hardware list or security/performance guarantees.
See `CLAUDE_HANDOFF.md` for actual build and boot results.
