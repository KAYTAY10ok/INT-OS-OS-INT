SUMMARY = "Unprivileged headless desktop checks for the disposable INT VM"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-desktop-user-check"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "sway-1.11 foot fuzzel dbus jq wayland-utils coreutils util-linux-setsid"
do_install() {
    install -Dm0755 ${S}/int-desktop-user-check ${D}${libexecdir}/int-desktop-user-check
}
