# Shared INT Desktop direction

One shared Wayland/tiling desktop is planned for both editions. Prototype Sway
with maintained terminal, bar, launcher and notification components before adding
an INT dashboard. Dark navy/black, blue/cyan accents, thin borders, compact data
and original ASCII branding follow the four references in `docs/design/references`.
Do not copy third-party artwork or logos from those references.

The prototype includes a compositor, theme, terminal profile and session wrapper.
Resource cost, accessibility, suspend, displays and input behavior require real
graphical-seat testing. OS-INT may add investigation panels to this foundation.
The [integration plan](docs/development/desktop-integration-plan.md) identifies
the pinned meta-wayland layer and stable Sway 1.11/wlroots 0.19.3, foot, fuzzel
and swaybar. Their recipes/configuration are now integrated in `meta-int-desktop`;
effective source/CPU/feature/ABI checks pass. The image and headless VM now pass
with a real non-root Sway session and terminal; see the
[validation record](docs/development/validation-desktop-2026-11-06.md). Use the
separate profile documented in `BUILDING.md`; graphical seat/input tests remain
necessary after headless compositor/client verification.
