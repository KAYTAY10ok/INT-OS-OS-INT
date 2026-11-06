SUMMARY = "Account and firewall checks for the disposable INT core VM"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-core-smoke file://int-core-smoke.service file://int-core-root-check file://firewall-check file://firewall-service-check file://int-net-probe.c"
S = "${UNPACKDIR}"
inherit systemd
SYSTEMD_SERVICE:${PN} = "int-core-smoke.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"
RDEPENDS:${PN} = "int-firstboot nftables iproute2 kernel-module-veth glibc-utils coreutils"
do_compile() {
    ${CC} ${CPPFLAGS} ${CFLAGS} -std=c11 -Wall -Wextra -Werror ${S}/int-net-probe.c ${LDFLAGS} -o int-net-probe
}
do_install() {
    install -Dm0644 ${S}/int-core-smoke.service ${D}${systemd_system_unitdir}/int-core-smoke.service
    install -Dm0755 ${S}/int-core-smoke ${D}${libexecdir}/int-core-smoke
    install -Dm0755 ${S}/int-core-root-check ${D}${libexecdir}/int-core-root-check
    install -Dm0755 ${S}/firewall-check ${D}${libexecdir}/int-core-test/firewall-check
    install -Dm0755 ${S}/firewall-service-check ${D}${libexecdir}/int-core-test/firewall-service-check
    install -Dm0755 int-net-probe ${D}${libexecdir}/int-core-test/int-net-probe
}
