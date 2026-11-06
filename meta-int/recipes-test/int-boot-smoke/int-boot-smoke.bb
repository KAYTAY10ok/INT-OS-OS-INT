SUMMARY = "Serial-console checks for the disposable INT QEMU image"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-boot-smoke file://int-boot-smoke.service"
S = "${UNPACKDIR}"
inherit allarch systemd
SYSTEMD_SERVICE:${PN} = "int-boot-smoke.service"
SYSTEMD_AUTO_ENABLE = "enable"
RDEPENDS:${PN} = "iproute2 glibc-utils"
do_install() {
    install -Dm0755 ${S}/int-boot-smoke ${D}${libexecdir}/int-boot-smoke
    install -Dm0644 ${S}/int-boot-smoke.service ${D}${systemd_system_unitdir}/int-boot-smoke.service
}
