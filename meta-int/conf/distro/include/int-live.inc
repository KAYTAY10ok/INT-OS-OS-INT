# Real-hardware live/installer profile. Include only from build-live, after
# int-desktop.inc. It keeps the validated QEMU profiles untouched.

# UEFI (and legacy BIOS) boot of the live ISO and of installed systems.
MACHINE_FEATURES:append = " efi pcbios"
EFI_PROVIDER = "grub-efi"
# The ISO offers "boot" (live session) and "install" (OE disk installer).
LABELS_LIVE = "boot install"
# Real PCs need their own drivers; give this kernel ABI its own identity.
SRC_URI:append:pn-linux-yocto = " file://int-hardware.cfg"
LINUX_VERSION_EXTENSION:pn-linux-yocto = "-int-live1"
PR:pn-linux-yocto = "r3"
# Live initramfs: OE live/BIOS-install modules, the INT UEFI installer, plus a writable memory overlay for
# the live session (the OE default leaves the live root read-only, so owner
# enrollment could not create an account).
INITRAMFS_SCRIPTS = "initramfs-framework-base initramfs-module-setup-live initramfs-module-udev initramfs-module-install int-installer int-live-overlay"
# Installer language and keyboard choices need these locales on the target.
GLIBC_GENERATE_LOCALES:pn-glibc-locale = "en_US.UTF-8 fr_FR.UTF-8 fr_CH.UTF-8 de_CH.UTF-8"
# Hyprland image loading: PNG/JPEG/WebP only (no HEIF/JPEG XL/librsvg builds).
PACKAGECONFIG:pn-hyprgraphics = ""
