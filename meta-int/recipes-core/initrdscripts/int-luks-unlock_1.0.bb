SUMMARY = "Unlock an INT LUKS2 root in the initramfs (initramfs-framework module)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://luksunlock"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "initramfs-framework-base cryptsetup"
do_install() {
    # After udev (01), before rootfs (90) mounts the unlocked root.
    install -Dm0755 ${S}/luksunlock ${D}/init.d/85-luksunlock
}
FILES:${PN} = "/init.d/85-luksunlock"
