# The application owns its global XDG configuration, avoiding an RPM file
# conflict with int-desktop-config. Both copies use one reviewed source file.
FILESEXTRAPATHS:prepend := "${THISDIR}/../../recipes-desktop/int-desktop-config/files:"
SRC_URI:append = " file://foot.ini;subdir=int-theme"
do_install:append() {
    install -Dm0644 ${UNPACKDIR}/int-theme/foot.ini ${D}${sysconfdir}/xdg/foot/foot.ini
}
CONFFILES:${PN}:append = " ${sysconfdir}/xdg/foot/foot.ini"
