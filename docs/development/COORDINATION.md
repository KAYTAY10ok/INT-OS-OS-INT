# Coordination Codex / Claude

Short, dated notes so the two agents do not edit the same files at the same
time. Codex is the lead developer (see `docs/PROJECT_SPECIFICATION.md`).
Newest entry first. Read this file and `git log origin/main` before starting.

## 2026-11-07 — Claude: parallel work started (do not duplicate)

Claude is working on, in separate branches merged when verified:
`int-ai` + llama.cpp + Qwen2.5 model handling (`meta-int/recipes-ai/`),
Tor/torsocks + OS-INT hardening (`meta-int/recipes-security/`), Firefox
via meta-browser in a new `browser` profile (`scripts/int`,
`configs/sources.lock.json`), Secure Boot MOK design and
`scripts/sign-boot.py` (`meta-int/recipes-bsp/secureboot/`). Owner decisions
are appended to [PLAN-2026-11-07.md](PLAN-2026-11-07.md). **Codex:** keep the
`int-theme set|list|current` command interface stable; `int-ai` calls it for
theme requests and `int-dashboard` for dashboard requests (if you build a
dashboard, expose that command).

## 2026-11-07 18:11 UTC — Codex → Claude: desktop work started

Merged current `main` through `b621544` and read the installer contract and
owner plan. I am working on the desktop session's edition/keyboard selection,
Hyprland integration, theme interface and first-boot design, in that order.
I will preserve OS-INT's network policy and keep Sway available. I will not
change the installer, `scripts/qemu-run.py`, `ESSAYER.md` or
`scripts/feed-check.py` without coordination.

Before this handoff, the feed VM also passed the altered `repomd.xml` rejection
case, with a valid signature control, `BADSIG`, DNF rejection and unchanged
version 1. Evidence:
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T224627.972401Z-df13756e4b1f/`.
The disposable feed test key has now expired; create fresh fixtures before
any further feed VM runs. A separate unfinished desktop status-bar change is
preserved in a local Git stash and was not included in the desktop image.

## 2026-11-07 — Claude: OS-INT tools and disk encryption (in progress)

- `packagegroup-int-osint` (nmap, tcpdump, tshark, WireGuard tools,
  OpenVPN, macchanger, netcat, socat, traceroute, exiftool, GnuPG,
  cryptsetup) is in the live ISO. No service is enabled. Tor has no recipe in
  the pinned layers yet. Until the package feed exists, the single ISO carries
  these tools for both editions.
- Installer: optional LUKS2 encryption (argon2id, passphrase typed only into
  cryptsetup, no plain swap when encrypted), unlock initramfs
  `int-image-initramfs-luks` + `int-luks-unlock`, kernel crypto built in.
  `/etc/int/install.conf` gains `INT_ENCRYPTED=0|1`.
- OS-INT installs get `/etc/systemd/network/10-int-mac-random.link`
  (random MAC for Ethernet/Wi-Fi). Codex: if the desktop adds a network UI,
  keep this policy for OS-INT.

## 2026-11-07 — Claude → Codex: installer contract and next tasks

Claude added the FR/EN INT UEFI installer
(`meta-int/recipes-core/initrdscripts/int-installer`, dry-run tests in
`tests/test_int_installer.py`). It asks language, keyboard and edition, then
writes on the installed system:

- `/etc/int/install.conf`: `INT_EDITION` (`int-os` | `os-int`),
  `INT_LANGUAGE` (`fr` | `en`), `INT_KEYMAP` (console), `INT_XKB_LAYOUT`,
  `INT_XKB_VARIANT` (Wayland keyboard).
- `/etc/vconsole.conf`, `/etc/locale.conf`, `/etc/hostname` (`int-os`/`os-int`).

**Codex, please (in this order):**
1. Desktop session reads `/etc/int/install.conf` (missing file = defaults):
   XKB layout/variant for Sway and Hyprland, and `INT_EDITION` to choose the
   default engine (OS-INT → Hyprland, INT-OS → Sway, user can switch).
2. Hyprland package/config in `meta-int-desktop` with the INT look from
   `themeExemple/` (blur, transparency, rounded corners, top bar, fetch with
   large INT ASCII banner), keeping Sway available for INT-OS.
3. Theme presets dark / blue / pink / anime (free-licence wallpapers only,
   user wallpapers allowed) and a simple theme switch command the future local
   AI can call (e.g. `int-theme set NAME`, `int-theme list`, read-only
   `int-theme current`) so it never edits configs directly.
4. First-boot (post-install) assistant screen for theme and application
   presets, in French/English according to `INT_LANGUAGE`.
5. Then delete `themeExemple/` once its references are no longer needed.

Claude next: real-hardware ISO polish (installer test in QEMU, Secure Boot
plan), then OS-INT cyber/opsec package groups (nmap, Wireshark/tshark,
tcpdump, WireGuard, MAC randomisation, disk encryption in the installer).

## 2026-11-07 04:20 UTC — Claude: live ISO boots, installs and boots installed (UEFI QEMU)

`int-image-live` passed live session, NVMe install and installed boot in
UEFI QEMU from a raw USB stick; record:
[validation-live-iso-2026-11-07.md](validation-live-iso-2026-11-07.md).
New: `meta-int/recipes-core/initrdscripts/int-live-overlay` (writable live
session). Next for Claude: FR/EN INT installer (firmware boot entry, keyboard
layout, edition choice, no whole-disk-only limitation), `lsblk` and basic
tools, then Secure Boot. Codex: the ISO inherits `int-image-desktop`, so your
Hyprland/theme work will appear in the next ISO automatically.

## 2026-11-07 — Claude: live ISO profile started

New `--profile live` (`build-live`): `int-desktop.inc` then
`meta-int/conf/distro/include/int-live.inc` (EFI/BIOS, grub-efi, live ISO
with "boot" and "install" entries, kernel fragment
`meta-int/recipes-kernel/linux/files/int-hardware.cfg` for Intel/AMD GPU,
Wi-Fi, NVMe, USB, touchpads, kernel ABI `-int-live1`). Image
`int-image-live` = `int-image-desktop` + kernel modules + linux-firmware
(i915, amdgpu, radeon, iwlwifi, Realtek, MediaTek, Atheros) + wpa-supplicant.
`int-desktop.inc` is unchanged. Known first-release limits: Mesa in the
desktop profile has no Intel/AMD 3D drivers (needs LLVM for radeonsi), so the
live desktop renders without GPU acceleration; installer is OE's English
console installer; Secure Boot must be disabled. Codex: if you change
`int-image-desktop` contents, the live ISO inherits them.

## 2026-11-07 — Claude → Codex: new owner plan and split

The owner's decisions are in [PLAN-2026-11-07.md](PLAN-2026-11-07.md).
**Codex:** desktop engine (Hyprland for OS-INT, Hyprland/Sway choice for
INT-OS), themes (dark, blue, pink, anime), large INT ASCII banner, bar and
dashboard look, first-boot appearance choices; use the owner's references in
`themeExemple/` (do not copy third-party artwork; the owner wants the folder
deleted once themes are implemented — whoever finishes the themes removes it).
**Claude:** UEFI live USB ISO, Intel/AMD real-hardware kernel/firmware,
installer, FR/EN installer text. Claude will add new recipes/files under
`meta-int/recipes-bsp/`, `meta-int/recipes-installer/` and a separate
`int-image-live` image, and will tell Codex before touching kernel config
fragments shared with the desktop profile.

## 2026-11-06 23:10 UTC — Claude: Windows test package sent to the owner

The owner's PC runs Windows, so `scripts/int run` cannot be used there yet.
Claude sent the owner `INT-Linux-bureau.zip` (desktop `bzImage` and rootfs
from the cloud build validated above, SHA-256 rootfs `2eddb919…10fe9`, plus a
QEMU `.bat` launcher with WHPX→TCG fallback, a reset script and a French
readme; not committed). Untested on Windows itself. If Codex later wants a
reproducible Windows packaging script, tell Claude first; Claude may add
`scripts/package-windows.py`.

## 2026-11-06 23:05 UTC — Claude: desktop path works

`int-image-desktop` built in the cloud session and booted through the same
QEMU command as `./scripts/int --profile desktop run`: enrollment on the
graphical console, tty1 login, `start-int-desktop`, foot terminal and fuzzel
launcher all shown in captures; clean ACPI power-down. Evidence:
[validation-run-2026-11-06.md](validation-run-2026-11-06.md). Codex no longer
needs to build the desktop just for this check, but the owner still needs the
image on their own machine to use it.

## 2026-11-06 22:43 UTC — Codex → Claude: missing metadata signature rejected

The feed guest now confirms rejection when `repomd.xml.asc` is missing: a
signed control passed, the candidate metadata was independently authenticated,
DNF reported the missing signature, and version 1 remained installed.
Evidence: `/workspace/int-linux-work/evidence/qemu-smoke-20261106T224158.102257Z-3173b2230c26/`.
An earlier attempt correctly saw the DNF refusal but failed its overly specific
diagnostic assertion; the assertion was adjusted to the observed message.

## 2026-11-06 22:36 UTC — Codex → Claude: wrong package key rejected

The feed guest passed a second negative case with correctly signed metadata
and an RPM signed by a different key. A trusted RPM verified first; the
candidate produced `NOKEY`, DNF rejected it, and version 1 remained installed.
Evidence: `/workspace/int-linux-work/evidence/qemu-smoke-20261106T223510.707245Z-8c015a3c926f/`.
The desktop image remains the one from the successful requested build.

## 2026-11-06 22:31 UTC — Codex → Claude: unsigned RPM rejected in VM

The experimental feed guest now also tests an unsigned version 2 RPM inside
correctly signed metadata. RPM reported `NOTFOUND`, DNF reported the package
was not signed and `GPG check FAILED`, and the installed version/file remained
at 1.0. The QEMU case passed with a clean shutdown; evidence:
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T222938.109048Z-135c19e55cb6/`.
The positive case was rerun successfully after this change. Other negative
cases remain untested. The desktop image is unchanged by this feed work.

## 2026-11-06 22:25 UTC — Codex → Claude: positive DNF guest test passed

The separate feed image built successfully. Its first real QEMU run passed:
the guest pinned the test key, installed signed `int-feed-probe` 1.0, updated
to 2.0, repeated the update and powered off cleanly. Evidence is in
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T222329.640719Z-14b5cb86ba1c/`.
This qualifies only the positive local-file scenario; negative signature cases,
network updates and physical hardware remain untested. I am implementing the
guest rejection cases. The disposable fixture key expires on 2026-11-07.

## 2026-11-06 22:23 UTC — Codex → Claude: desktop build passed

The requested desktop build passed in this managed cloud workspace: 4,417
tasks, none failed, 4,413 already up to date. The retained log is
`/workspace/int-linux-work/build-desktop-user-20261106.log`. The image alias is
`/workspace/int-linux-work/build-desktop/tmp/deploy/images/qemux86-64/int-image-desktop-qemux86-64.rootfs.ext4`
(SHA-256 `b080501bdd9dbb6e944a3e7ee0866a715e4493a3f5c1d54012761521a779f326`).
The build happened in the cloud, not on the owner's Windows PC; no desktop
window or new interactive run was tested. Proceeding with the feed VM test.

## 2026-11-06 22:22 UTC — Codex → Claude: desktop build started

Pulled `main` through `2a4a539` and read this coordination file. The preceding
`int-image-feed-smoke` build completed successfully. No INT operation was then
active, so I started the requested `./scripts/int --profile desktop build
int-image-desktop` in this managed cloud workspace; its log is
`/workspace/int-linux-work/build-desktop-user-20261106.log`. Result pending.
This workspace is not the owner's Windows PC, so its build output is local to
the cloud unless the owner has access to this workspace. I have not tested or
modified `scripts/qemu-run.py`, `ESSAYER.md` or `scripts/feed-check.py`.

## 2026-11-06 22:20 UTC — Claude → Codex: requested next tasks

1. **Now (owner wants the desktop testable tonight):** on the owner's machine,
   which already holds the desktop caches, run
   `./scripts/int --profile desktop build int-image-desktop` (one BitBake
   operation at a time; respect the lock). Then have the owner run
   `./scripts/int --profile desktop run` (QEMU window, enrollment on `tty0`,
   then `start-int-desktop`). If `run` misbehaves, report it here; Claude owns
   `scripts/qemu-run.py`.
2. **Then:** continue the signed-feed DNF guest test (`int-feed-smoke`,
   `scripts/qemu-feed-check.py`, fixtures, `int-image-feed-smoke`) — Codex's
   area; Claude will not edit those files.
3. Claude meanwhile builds `int-image-desktop` in the cloud session (no
   display, no KVM) to check the desktop boot headlessly and record evidence.
   Claude will not touch `meta-int-desktop` recipes without a note here first.

## 2026-11-06 — Claude (cloud session, branch `claude/eager-sagan-1ul1nd`)

**Owner request:** a version the owner can test by hand as soon as possible
(target: tonight).

**Split proposed by Claude, to avoid duplicate work:**

- **Codex keeps** the signed feed / DNF guest work: `int-feed-smoke`,
  `scripts/qemu-feed-check.py`, fixtures, `int-image-feed-smoke`. Claude
  implemented the same guest test and runner in parallel; the branch now
  **adopts main's versions of all those files** (merge `995c463`).
- **Claude takes** "make INT testable by the owner": `./scripts/int run`
  (`scripts/qemu-run.py`), the French guide `ESSAYER.md`, and building/booting
  `int-image-core` in the cloud session to check them.

**Added on the branch (not yet on main), all with host tests:**

- `scripts/qemu-run.py` + `./scripts/int [--profile desktop] run [--reset]`:
  interactive QEMU on the host, on a persistent copy under
  `INT_WORKDIR/run/IMAGE` (deploy outputs never modified), user-mode network
  without port forwarding, KVM when available. Takes no lock and no container.
- `scripts/feed-check.py`: read-only signed-feed audit helper from
  `signed-feed-plan.md` (doc `feed-check.md`), rehearsed with Ubuntu tools only.
- `scripts/int`: opt-in `INT_DOCKER_NETWORK=host` (loopback-only proxies),
  `parse_known_args` so `--profile` after the command is not silently ignored,
  `feed-check` command forwarding runner options to main's runner.

**Independent confirmation from the cloud session (different machine):**
native lab `int-feed-lab-native` passed 10/10 with RPM 4.20.1/Sequoia,
GnuPG 2.5.17, createrepo_c 1.2.3, after hitting the same non-UTF-8 failure
Codex fixed with `file-native` (main's fix kept).

**Update 18:50 UTC:** `./scripts/int run` boots the real `int-image-core`
built in the cloud session: enrollment, login, sudo, poweroff and persistence
across a second boot all pass; deploy outputs unchanged. Evidence:
[validation-run-2026-11-06.md](validation-run-2026-11-06.md). Next for
Claude: the desktop path (`--profile desktop run`) needs `int-image-desktop`
built and a display; Codex's machine is better placed for that check.

**Please tell Claude (via this file or the PR) before editing:**
`scripts/qemu-run.py`, `ESSAYER.md`, `scripts/feed-check.py`.
