SUMMARY = "Console enrollment of the first INT owner"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-firstboot file://int-firstboot.service file://10-int-firstboot.conf file://int-owner"
S = "${UNPACKDIR}"
inherit allarch systemd
SYSTEMD_SERVICE:${PN} = "int-firstboot.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"
RDEPENDS:${PN} = "busybox shadow sudo glibc-utils"
do_install() {
    install -Dm0755 ${S}/int-firstboot ${D}${libexecdir}/int-firstboot
    install -Dm0644 ${S}/int-firstboot.service ${D}${systemd_system_unitdir}/int-firstboot.service
    for unit in getty@ serial-getty@; do
        install -Dm0644 ${S}/10-int-firstboot.conf ${D}${systemd_system_unitdir}/$unit.service.d/10-int-firstboot.conf
    done
    # Match upstream sudo's directory mode, including in the RPM file records.
    install -d -m0750 ${D}${sysconfdir}/sudoers.d
    install -m0440 ${S}/int-owner ${D}${sysconfdir}/sudoers.d/int-owner
}
FILES:${PN}:append = " ${systemd_system_unitdir}/getty@.service.d ${systemd_system_unitdir}/serial-getty@.service.d ${sysconfdir}/sudoers.d/int-owner"
CONFFILES:${PN} = "${sysconfdir}/sudoers.d/int-owner"
