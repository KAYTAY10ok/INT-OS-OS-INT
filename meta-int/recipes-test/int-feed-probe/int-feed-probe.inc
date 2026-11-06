SUMMARY = "Disposable version marker for package-feed tests"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit allarch

do_install() {
    install -d ${D}${datadir}/int-feed-probe
    printf '%s\n' '${PV}' > ${D}${datadir}/int-feed-probe/version
}
