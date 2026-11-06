SUMMARY = "Virtio graphical console checks for the disposable INT VM"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-graphics-root-check"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "int-firstboot systemd-extra-utils sudo jq sway-1.11 foot coreutils"
do_install() {
    install -Dm0755 ${S}/int-graphics-root-check ${D}${libexecdir}/int-graphics-root-check
}
