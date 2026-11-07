SUMMARY = "INT live session writable memory overlay (initramfs-framework module)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://liveoverlay"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "initramfs-framework-base"
do_install() {
    # After 90-rootfs mounts the image, before 99-finish switches root.
    install -Dm0755 ${S}/liveoverlay ${D}/init.d/91-liveoverlay
}
FILES:${PN} = "/init.d/91-liveoverlay"
