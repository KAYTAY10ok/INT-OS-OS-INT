FILESEXTRAPATHS:prepend := "${THISDIR}/../../recipes-desktop/int-desktop-config/files:"
SRC_URI:append = " file://fuzzel.ini;subdir=int-theme"
do_install:append() {
    install -Dm0644 ${UNPACKDIR}/int-theme/fuzzel.ini ${D}${sysconfdir}/xdg/fuzzel/fuzzel.ini
}
FILES:${PN}:append = " ${sysconfdir}/xdg/fuzzel/fuzzel.ini"
CONFFILES:${PN}:append = " ${sysconfdir}/xdg/fuzzel/fuzzel.ini"
