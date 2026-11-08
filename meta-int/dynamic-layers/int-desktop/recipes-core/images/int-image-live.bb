require recipes-core/images/int-image-desktop.bb

SUMMARY = "INT Linux live/installer ISO for real Intel/AMD PCs"
DESCRIPTION = "UEFI live USB image of the shared desktop with real-hardware drivers and firmware. Boot entry 'boot' runs the live session; 'install' runs the OE disk installer. Build with --profile live."
COMPATIBLE_MACHINE = "^qemux86-64$"

# "iso" only: the extra "hddimg" from "live" is not needed and doubles the space.
IMAGE_FSTYPES = "iso"
# Hide kernel messages so the enrollment prompt stays readable.
APPEND:append = " quiet loglevel=3"
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
    wireless-regdb-static \
    kbd \
    kbd-keymaps \
    util-linux-lsblk \
    packagegroup-int-osint \
    int-luks-initrd \
    int-ai \
    int-ai-setup \
    llama-cpp \
    procps \
    int-apps \
    int-wifi \
    ${INT_APP_PRESET_PACKAGES} \
"
# Packages of the "media" presets in int-apps (kept or removed at first start).
# tests/test_int_apps.py checks this list against the preset files.
INT_APP_PRESET_PACKAGES = " \
    htop btop nano tmux zsh rsync unzip \
    grim slurp wl-clipboard mako swaylock swayidle brightnessctl \
    git make strace gdb \
    int-audio \
"
# Keep the rpm database (and dnf) so int-apps can remove presets offline and
# install feed presets once an INT feed is configured. No feed is configured.
IMAGE_FEATURES += "package-management"
# The installer creates a disk-sized partition; the live rootfs needs little slack.
IMAGE_ROOTFS_EXTRA_SPACE = "65536"
# The live rootfs is read-only (tmpfs overlay) and the installer creates its own
# filesystem, so the default 30% free-space overhead only enlarges the ISO.
IMAGE_OVERHEAD_FACTOR = "1.05"
# Locales offered by the installer (French/English, Swiss/German keyboards).
IMAGE_LINGUAS = "en-us fr-fr fr-ch de-ch"
