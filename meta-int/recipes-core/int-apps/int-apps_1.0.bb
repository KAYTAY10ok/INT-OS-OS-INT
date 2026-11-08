SUMMARY = "INT application presets (int-apps)"
DESCRIPTION = "Lists, installs and removes groups of applications. Presets shipped on the ISO are kept or removed offline at the first desktop start; feed presets wait for the INT package feed."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = " \
    file://int-apps \
    file://presets/cyber.preset \
    file://presets/opsec.preset \
    file://presets/terminal.preset \
    file://presets/desktop-tools.preset \
    file://presets/dev.preset \
    file://presets/web.preset \
    file://presets/audio.preset \
    file://presets/multimedia.preset \
"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "python3-core rpm sudo"
do_install() {
    install -Dm0755 ${S}/int-apps ${D}${bindir}/int-apps
    install -d ${D}${datadir}/int/apps
    install -m0644 ${S}/presets/*.preset ${D}${datadir}/int/apps/
}
FILES:${PN} = "${bindir}/int-apps ${datadir}/int/apps"
