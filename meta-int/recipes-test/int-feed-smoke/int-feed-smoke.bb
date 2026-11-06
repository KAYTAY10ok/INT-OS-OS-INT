SUMMARY = "Serial-console signed-feed DNF test for the disposable INT QEMU image"
DESCRIPTION = "Test-only oneshot service. Install only in int-image-feed-smoke; never in normal images."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-feed-smoke file://int-feed-smoke.service"
S = "${UNPACKDIR}"
inherit allarch systemd
SYSTEMD_SERVICE:${PN} = "int-feed-smoke.service"
SYSTEMD_AUTO_ENABLE = "enable"
RDEPENDS:${PN} = "python3-core python3-io python3-shell python3-crypt rpm dnf gnupg util-linux-blkid util-linux-mount"
do_install() {
    install -Dm0755 ${S}/int-feed-smoke ${D}${libexecdir}/int-feed-smoke
    install -Dm0644 ${S}/int-feed-smoke.service ${D}${systemd_system_unitdir}/int-feed-smoke.service
}
