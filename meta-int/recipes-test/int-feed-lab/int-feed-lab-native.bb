SUMMARY = "Isolated RPM and repository signature laboratory"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-feed-lab.py"
S = "${UNPACKDIR}"

inherit native

DEPENDS = "rpm-native gnupg-native createrepo-c-native python3-native"

# This is a test, not a distributable signing service. A fresh temporary key
# and fixture are created for every invocation and deleted after the test.
do_compile[nostamp] = "1"
do_compile() {
    ${STAGING_BINDIR_NATIVE}/python3 ${S}/int-feed-lab.py \
        --bindir ${STAGING_BINDIR_NATIVE} > ${T}/feed-lab-output.txt
    # Replay the report to the BitBake console so callers can retain it even
    # when rm_work later removes the recipe's temporary task log.
    bbplain "$(cat ${T}/feed-lab-output.txt)"
}

do_install() {
    :
}
