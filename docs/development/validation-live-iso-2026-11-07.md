# Live/installer ISO validation — 2026-11-07 UTC

First real-boot milestone: `int-image-live` (`./scripts/int --profile live
build int-image-live`), the shared desktop as a UEFI live ISO with OE's
console disk installer, real-hardware kernel drivers and firmware. Tested in
QEMU as close to a physical PC as this cloud session allows; **no physical
PC has booted it yet.**

## Artifact

| Item | Value |
| --- | --- |
| ISO | `int-image-live-qemux86-64.rootfs-20261107031048.iso`, 1,383,071,744 bytes |
| ISO SHA-256 | `0ef01280eb156fb552aa4ba6247a54e475970fe7606f51ce8f0db2d1bd1f2e38` |
| Compressed copy sent to the owner | `INT-Linux-0.1-live.iso.xz`, SHA-256 `986eebfbc67ee9b707cdbe5002c0f57fdb199b90dc05f25f34f6d27f0c76ccf7` |
| Kernel | 6.18.54, `-int-live1`, `r3`, fragment `int-hardware.cfg` |
| Layout | Hybrid ISO: MBR + GPT with an EFI system partition (raw-writable to USB), isolinux for legacy BIOS |

Build: 4,857 tasks succeeded after two fixes found by testing (below). The
cloud disk limit required `iso` instead of `live` (no extra `hddimg`), a
smaller rootfs slack, and a session-local lower disk-monitor threshold.

## Test setup

QEMU 8.2.2 TCG, q35, 4 vCPUs, 3 GiB, OVMF UEFI firmware (Ubuntu EDK II),
`std` VGA, xHCI with USB keyboard/tablet, Intel `e1000e` NIC, the **ISO
attached raw as a USB mass-storage stick** (as written by Rufus DD mode /
dd), and an empty 16 GiB **NVMe** target disk. A scripted user typed real
key events through QMP and took screen captures.

## Results

1. **Live session ("boot", GRUB default):** UEFI booted the stick; the
   `e1000e` real-hardware driver loaded and the link came up. Owner
   enrollment on the screen, tty1 login (`uname -r` = `6.18.54-int-live1`),
   `start-int-desktop` showed the INT Sway session, Super+Return opened a
   terminal, ACPI power-down, QEMU exit 0
   ([enrollment](evidence/live-iso-enrollment-2026-11-07.png),
   [desktop](evidence/live-iso-desktop-2026-11-07.png)).
2. **Installer ("install"):** it listed `/dev/nvme0n1`, accepted the
   target, created GPT (55.6 MB EFI, 16.3 GB ext4 root, 858 MB swap),
   copied the system and GRUB, and reported "Installation successful"
   ([target](evidence/live-iso-installer-target-2026-11-07.png),
   [done](evidence/live-iso-installer-done-2026-11-07.png)).
3. **Installed system (NVMe only, stick removed):** firmware → GRUB →
   INT Linux; enrollment, login (`6.18.54-int-live1`), desktop and terminal,
   clean power-off, QEMU exit 0
   ([login](evidence/live-iso-installed-login-2026-11-07.png),
   [desktop](evidence/live-iso-installed-desktop-2026-11-07.png)).

## Defects found and fixed

- The OE live initramfs left the live root **read-only**: enrollment failed
  (`useradd: cannot lock /etc/passwd`), so no login prompt appeared. Fixed by
  `int-live-overlay` (tmpfs overlay for the live entry only).
- Kernel messages buried the enrollment prompt: `quiet loglevel=3` added.
- Missing Wi-Fi regulatory database: `wireless-regdb-static` added.

## Known limits (first release)

- With the NVRAM left from the USB boot, OVMF fell into its UEFI shell after
  the stick was removed; with fresh NVRAM it booted the disk. The OE
  installer only relies on the removable path `\EFI\BOOT\BOOTX64.EFI` and
  creates no firmware boot entry. The INT installer must add one
  (`efibootmgr`). Some real PCs may need the disk chosen in the boot menu.
- Secure Boot is not supported yet (unsigned GRUB): disable it on test PCs.
- No GPU 3D acceleration (Mesa without Intel/AMD drivers); the desktop uses
  software rendering. Real Intel/AMD GPUs use their kernel KMS drivers.
- The installer is OE's English console installer and erases the whole
  target disk. Missing tools noticed: `lsblk`.
- Only QEMU devices were exercised: real Wi-Fi, touchpads, sound, GPUs,
  suspend and NVIDIA remain untested.

## Update: INT French/English installer (same day, later build)

ISO rebuilt with `int-installer` replacing OE's install-efi module (SHA-256
recorded in the commit that adds this section is the 17:02 UTC build).
Same UEFI QEMU setup (raw ISO as USB stick, empty 16 GiB NVMe, fresh NVRAM):

1. GRUB "install" entry → bilingual language prompt, then French menus:
   keyboard (Swiss French chosen), edition (OS-INT chosen), numbered disk
   list showing `/dev/nvme0n1 16 GiB QEMU NVMe Ctrl`, warning, and re-typed
   number confirmation ([questions](evidence/int-installer-questions-2026-11-07.png)).
2. Layout created: 512 MiB EFI, 12,959 MiB ext4, 2,913 MiB swap (RAM-sized);
   system copied; `efibootmgr` created `Boot0003* INT Linux
   HD(1,GPT,...)/\EFI\BOOT\BOOTX64.EFI`, then "Installation reussie"
   ([firmware entry](evidence/int-installer-firmware-entry-2026-11-07.png)).
3. Installed system booted from NVMe: hostname `os-int` from the edition
   choice, enrollment and login worked, and the Swiss French console keymap
   was active (the test's US key codes produced QWERTZ characters)
   ([installed](evidence/int-installer-installed-os-int-2026-11-07.png)).

Open point: after the next power-on, OVMF no longer listed `INT Linux` and
started its UEFI shell before the disk (the NVRAM order came from the USB
boot). This looks specific to OVMF's handling of QEMU's own boot order; the
installed system booted when the NVMe disk was given boot priority. Real-PC
behaviour of the created entry is still to be observed. The desktop launch on
an installed system was validated in the previous section (OE installer).
