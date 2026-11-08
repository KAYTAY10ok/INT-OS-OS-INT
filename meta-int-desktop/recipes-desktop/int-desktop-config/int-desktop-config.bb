SUMMARY = "INT session launcher and shared desktop configuration"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://start-int-desktop file://int-status file://sway-config file://foot.ini file://fuzzel.ini file://int-desktop.desktop file://hyprland.conf file://int-session file://int-desktop-tools file://int-autostart.sh"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "busybox dbus systemd sway-1.11 foot fuzzel int-theme swaybg python3-core python3-json"
do_install() {
    install -Dm0755 ${S}/start-int-desktop ${D}${bindir}/start-int-desktop
    install -Dm0755 ${S}/int-status ${D}${libexecdir}/int-status
    install -Dm0644 ${S}/sway-config ${D}${sysconfdir}/int/sway/config
    install -Dm0644 ${S}/hyprland.conf ${D}${sysconfdir}/int/hypr/hyprland.conf
    install -Dm0755 ${S}/int-session ${D}${bindir}/int-session
    install -Dm0644 ${S}/int-autostart.sh ${D}${sysconfdir}/profile.d/int-autostart.sh
    install -Dm0755 ${S}/int-desktop-tools ${D}${libexecdir}/int-desktop-tools
    install -Dm0644 ${S}/foot.ini ${D}${sysconfdir}/int/foot.ini
    install -Dm0644 ${S}/fuzzel.ini ${D}${sysconfdir}/int/fuzzel.ini
    install -Dm0644 ${S}/int-desktop.desktop ${D}${datadir}/wayland-sessions/int-desktop.desktop
}
FILES:${PN}:append = " ${datadir}/wayland-sessions/int-desktop.desktop ${sysconfdir}/profile.d/int-autostart.sh"
CONFFILES:${PN} = "${sysconfdir}/int/hypr/hyprland.conf ${sysconfdir}/int/sway/config ${sysconfdir}/int/foot.ini ${sysconfdir}/int/fuzzel.ini"
