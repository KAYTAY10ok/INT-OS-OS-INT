SUMMARY = "INT Linux minimal console foundation"
DESCRIPTION = "Source-built glibc/systemd foundation, without a desktop or an unlocked root account."
LICENSE = "MIT"
inherit core-image
IMAGE_INSTALL = "packagegroup-core-boot systemd-networkd iproute2 os-release"
IMAGE_FEATURES = ""
IMAGE_ROOTFS_SIZE = "65536"
IMAGE_ROOTFS_EXTRA_SPACE = "16384"
