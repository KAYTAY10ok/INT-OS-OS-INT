SUMMARY = "OS-INT kernel/network hardening defaults and the int-privacy helper"
DESCRIPTION = "sysctl drop-in (kernel pointer and log restrictions, strict \
reverse-path filtering, no ICMP redirects, SYN cookies, Yama ptrace scope \
when the kernel has Yama) and the int-privacy command. Enables no service."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://90-int-osint.conf file://int-privacy"
S = "${UNPACKDIR}"
inherit allarch

do_install() {
    install -Dm0644 ${S}/90-int-osint.conf ${D}${nonarch_libdir}/sysctl.d/90-int-osint.conf
    install -Dm0755 ${S}/int-privacy ${D}${bindir}/int-privacy
}

FILES:${PN} = "${nonarch_libdir}/sysctl.d/90-int-osint.conf ${bindir}/int-privacy"
# systemd-sysctl applies the drop-in; clean-metadata needs exiftool.
RDEPENDS:${PN} = "systemd"
RRECOMMENDS:${PN} = "exiftool"
