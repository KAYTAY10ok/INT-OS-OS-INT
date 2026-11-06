# Use upstream's one-shot service, with an INT-owned table and atomic reloads.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# The same upstream archive and pinned checksum are available over verified TLS.
SRC_URI:remove = "http://www.netfilter.org/projects/nftables/files/${BP}.tar.xz"
SRC_URI:prepend = "https://www.netfilter.org/projects/nftables/files/${BP}.tar.xz "
SRC_URI:append = " file://int-main.nft file://10-int-policy.conf file://10-int-firewall.conf"

inherit systemd

EXTRA_OECONF:append = " --with-unitdir=${systemd_system_unitdir}"
# The baseline needs the nft executable, not Python bindings or line editing.
PACKAGECONFIG:remove = "python readline"

SYSTEMD_SERVICE:${PN} = "nftables.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install:append() {
    install -d ${D}${sysconfdir}/nftables/rules
    install -m 0644 ${UNPACKDIR}/int-main.nft ${D}${sysconfdir}/nftables/rules/main.nft
    install -d ${D}${systemd_system_unitdir}/nftables.service.d
    sed -e 's|@SBINDIR@|${sbindir}|g' \
        -e 's|@SYSCONFDIR@|${sysconfdir}|g' \
        ${UNPACKDIR}/10-int-policy.conf \
        > ${D}${systemd_system_unitdir}/nftables.service.d/10-int-policy.conf
    chmod 0644 ${D}${systemd_system_unitdir}/nftables.service.d/10-int-policy.conf
    install -d ${D}${systemd_system_unitdir}/systemd-networkd.service.d
    install -m 0644 ${UNPACKDIR}/10-int-firewall.conf \
        ${D}${systemd_system_unitdir}/systemd-networkd.service.d/10-int-firewall.conf
}

FILES:${PN}:append = " ${sysconfdir}/nftables/rules/main.nft ${systemd_system_unitdir}/nftables.service.d ${systemd_system_unitdir}/systemd-networkd.service.d"
CONFFILES:${PN}:append = " ${sysconfdir}/nftables/rules/main.nft"
