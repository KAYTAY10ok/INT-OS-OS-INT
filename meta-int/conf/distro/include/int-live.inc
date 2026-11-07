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
