SUMMARY = "INT initramfs that unlocks a LUKS2 root, for encrypted installs"
LICENSE = "MIT"
PACKAGE_INSTALL = "initramfs-framework-base initramfs-module-udev initramfs-module-rootfs int-luks-unlock ${VIRTUAL-RUNTIME_base-utils} udev base-passwd ${ROOTFS_BOOTSTRAP_INSTALL}"
IMAGE_FEATURES = ""
PACKAGE_EXCLUDE = "kernel-image-*"
IMAGE_NAME_SUFFIX ?= ""
IMAGE_LINGUAS = ""
IMAGE_FSTYPES = "cpio.gz"
inherit core-image
IMAGE_ROOTFS_SIZE = "8192"
IMAGE_ROOTFS_EXTRA_SPACE = "0"
COMPATIBLE_HOST = '(x86_64.*|i.86.*)-(linux.*)'
