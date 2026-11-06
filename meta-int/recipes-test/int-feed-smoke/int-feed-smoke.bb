SUMMARY = "Disposable local package-feed guest test"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-feed-smoke file://int-feed-keycheck file://int-feed-args file://int-feed-smoke.service"
S = "${UNPACKDIR}"
inherit allarch systemd
SYSTEMD_SERVICE:${PN} = "int-feed-smoke.service"
SYSTEMD_AUTO_ENABLE = "enable"
# GPGME needs gpgconf from gnupg as well as gpg from gnupg-gpg.
RDEPENDS:${PN} = "dnf rpm gnupg gnupg-gpg"
do_install() {
    install -Dm0755 ${S}/int-feed-smoke ${D}${libexecdir}/int-feed-smoke
    install -Dm0755 ${S}/int-feed-keycheck ${D}${libexecdir}/int-feed-keycheck
    install -Dm0755 ${S}/int-feed-args ${D}${libexecdir}/int-feed-args
    install -Dm0644 ${S}/int-feed-smoke.service ${D}${systemd_system_unitdir}/int-feed-smoke.service
}
