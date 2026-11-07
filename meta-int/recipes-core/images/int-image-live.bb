require recipes-core/images/int-image-desktop.bb

SUMMARY = "INT Linux live/installer ISO for real Intel/AMD PCs"
DESCRIPTION = "UEFI live USB image of the shared desktop with real-hardware drivers and firmware. Boot entry 'boot' runs the live session; 'install' runs the OE disk installer. Build with --profile live."
COMPATIBLE_MACHINE = "^qemux86-64$"

IMAGE_FSTYPES = "live"
# A live rootfs must hold all kernel modules and common firmware.
IMAGE_INSTALL:append = " \
    kernel-modules \
    linux-firmware-i915 \
    linux-firmware-amdgpu \
    linux-firmware-radeon \
    linux-firmware-iwlwifi \
    linux-firmware-ibt \
    linux-firmware-rtl-nic \
    linux-firmware-rtl8168 \
    linux-firmware-rtl8822 \
    linux-firmware-rtl8852 \
    linux-firmware-mediatek \
    linux-firmware-ath10k \
    linux-firmware-ath11k \
    wpa-supplicant \
    iw \
"
IMAGE_ROOTFS_EXTRA_SPACE = "524288"
