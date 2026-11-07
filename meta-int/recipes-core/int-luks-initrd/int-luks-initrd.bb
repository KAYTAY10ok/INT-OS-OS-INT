SUMMARY = "Ship the INT LUKS unlock initramfs in the live image for the installer"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
INHIBIT_DEFAULT_DEPS = "1"
PACKAGE_ARCH = "${MACHINE_ARCH}"
do_install[depends] += "int-image-initramfs-luks:do_image_complete"
do_install() {
    install -Dm0644 ${DEPLOY_DIR_IMAGE}/int-image-initramfs-luks-${MACHINE}.cpio.gz \
        ${D}${libdir}/int/initrd-luks.cpio.gz
}
FILES:${PN} = "${libdir}/int/initrd-luks.cpio.gz"
