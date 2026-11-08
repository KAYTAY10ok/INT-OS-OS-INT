SUMMARY = "INT sound: PipeWire and WirePlumber started for every desktop user"
DESCRIPTION = "Enables the PipeWire socket and the WirePlumber session manager in the systemd user manager (OE installs the user units but does not enable them). Removing this package turns sound off; the int-apps 'audio' preset does that."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
inherit allarch
ALLOW_EMPTY:${PN} = "1"
RDEPENDS:${PN} = "pipewire pipewire-tools pipewire-alsa wireplumber"
do_install() {
    install -d ${D}${sysconfdir}/systemd/user/sockets.target.wants ${D}${sysconfdir}/systemd/user/pipewire.service.wants
    ln -s ${systemd_user_unitdir}/pipewire.socket ${D}${sysconfdir}/systemd/user/sockets.target.wants/pipewire.socket
    ln -s ${systemd_user_unitdir}/wireplumber.service ${D}${sysconfdir}/systemd/user/pipewire.service.wants/wireplumber.service
    ln -s ${systemd_user_unitdir}/wireplumber.service ${D}${sysconfdir}/systemd/user/pipewire-session-manager.service
}
FILES:${PN} = "${sysconfdir}/systemd/user"
