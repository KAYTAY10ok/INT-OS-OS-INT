SUMMARY = "INT Wi-Fi helper (int-wifi) and DHCP for wireless interfaces"
DESCRIPTION = "Scan, connect (hidden passphrase, only the WPA hash is stored), status and forget, on top of wpa_supplicant@IFACE and systemd-networkd."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-wifi file://25-int-wireless.network"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "wpa-supplicant wpa-supplicant-passphrase iw iproute2 sudo systemd-networkd"
do_install() {
    install -Dm0755 ${S}/int-wifi ${D}${bindir}/int-wifi
    install -Dm0644 ${S}/25-int-wireless.network ${D}${sysconfdir}/systemd/network/25-int-wireless.network
}
FILES:${PN} = "${bindir}/int-wifi ${sysconfdir}/systemd/network/25-int-wireless.network"
