SUMMARY = "Isolated RPM and repository signature laboratory"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-feed-lab.py file://int-feed-fixtures.py"
S = "${UNPACKDIR}"

inherit native python3native

DEPENDS = "rpm-native gnupg-native createrepo-c-native file-native"
# Match the native file binary with the native MAGIC database used by RPM.
EXTRANATIVEPATH += "file-native"

# This is a test, not a distributable signing service. A fresh temporary key
# and fixture are created for every invocation and deleted after the test.
do_compile[nostamp] = "1"
do_compile() {
    ${PYTHON} ${S}/int-feed-lab.py \
        --bindir ${STAGING_BINDIR_NATIVE} > ${T}/feed-lab-output.txt
    # Replay the report to the BitBake console so callers can retain it even
    # when rm_work later removes the recipe's temporary task log.
    bbplain "$(cat ${T}/feed-lab-output.txt)"
}

do_install() {
    :
}

# Explicit, opt-in task: caller supplies copied inputs and a new output name
# through a post-read configuration file. This does not run during do_build.
export INT_FEED_V1
export INT_FEED_V2
export INT_FEED_OUTPUT
do_create_feed_fixtures[nostamp] = "1"
do_create_feed_fixtures() {
    ${PYTHON} ${S}/int-feed-fixtures.py --bindir ${STAGING_BINDIR_NATIVE}
}
addtask create_feed_fixtures after do_unpack do_prepare_recipe_sysroot
