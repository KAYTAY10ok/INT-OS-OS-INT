SUMMARY = "INT hardened Firefox enterprise policies"
DESCRIPTION = "System-wide policies.json for Firefox: no telemetry or studies, strict tracking protection, DNS-over-HTTPS off unless the user enables it, no password-saving prompts and no automatic extension downloads."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://policies.json"
S = "${UNPACKDIR}"

inherit allarch

do_configure[noexec] = "1"
do_compile[noexec] = "1"

# Firefox on Linux reads /etc/firefox/policies/policies.json. The file is
# root-owned and read-only so a user session cannot weaken it.
do_install() {
    install -d ${D}${sysconfdir}/firefox/policies
    install -m 0644 ${S}/policies.json ${D}${sysconfdir}/firefox/policies/policies.json
}

FILES:${PN} = "${sysconfdir}/firefox/policies/policies.json"
# The policies are only useful with Firefox, but must not pull it into
# images by themselves; int-image-osint-browser installs both.
