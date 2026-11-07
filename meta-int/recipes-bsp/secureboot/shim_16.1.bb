SUMMARY = "shim: first-stage UEFI boot loader (unsigned INT build)"
DESCRIPTION = "Builds shim, MokManager and fallback from the upstream 16.1 \
release, unsigned. Real PCs accept such a shim under Secure Boot only if its \
signer is in firmware db: either Microsoft after an accepted shim-review \
submission, or the INT certificate enrolled by the user in firmware setup. \
This recipe is not used by any image yet; see docs/development/secure-boot.md."
HOMEPAGE = "https://github.com/rhboot/shim"
SECTION = "bootloaders"
# shim (BSD-2-Clause), its bundled gnu-efi (Intel EFI toolkit, BSD-style),
# EDK2 Cryptlib (BSD-2-Clause-Patent) and the OpenSSL subset it embeds.
LICENSE = "BSD-2-Clause & BSD-2-Clause-Patent & OpenSSL"
LIC_FILES_CHKSUM = "file://COPYRIGHT;md5=b92e63892681ee4e8d27e7a7e87ef2bc \
                    file://gnu-efi/README.efilib;md5=d234379cbdd5c97c64554da2fcd07a8e"

# Official release tarball (includes the gnu-efi submodule). Upstream tag
# 16.1 = commit afc49558b34548644c1cd0ad1b6526a9470182ed, also recorded in
# the tarball's "commit" file.
SRC_URI = "https://github.com/rhboot/shim/releases/download/${PV}/shim-${PV}.tar.bz2"
SRC_URI[sha256sum] = "46319cd228d8f2c06c744241c0f342412329a7c630436fce7f82cf6936b1d603"

S = "${UNPACKDIR}/shim-${PV}"

COMPATIBLE_HOST = "x86_64.*-linux"

inherit deploy

# Optional PUBLIC certificate (DER) to embed as shim's vendor certificate,
# e.g. set in local.conf to the owner's int-secureboot.cer. Never point this
# at a private key: shim only needs the certificate. Leave empty for a shim
# that trusts db and MOK only.
INT_SHIM_VENDOR_CERT ?= ""

# ENABLE_SHIM_CERT is deliberately not set: it would generate a private key
# inside the build tree to sign MokManager and fallback.
EXTRA_OEMAKE = " \
    ARCH=x86_64 \
    CROSS_COMPILE=${TARGET_PREFIX} \
    COMPILER=gcc \
    HOSTCC='${BUILD_CC}' \
    EFIDIR=INT \
    DASHJ='${PARALLEL_MAKE}' \
    ${@'VENDOR_CERT_FILE=' + d.getVar('INT_SHIM_VENDOR_CERT') if d.getVar('INT_SHIM_VENDOR_CERT') else ''} \
"

do_compile[file-checksums] += "${@(d.getVar('INT_SHIM_VENDOR_CERT') + ':True') if d.getVar('INT_SHIM_VENDOR_CERT') else ''}"

do_compile() {
    oe_runmake shimx64.efi mmx64.efi fbx64.efi
}

do_install() {
    install -d ${D}${datadir}/shim/x64
    install -m 0644 ${B}/shimx64.efi ${B}/mmx64.efi ${B}/fbx64.efi ${D}${datadir}/shim/x64/
}

do_deploy() {
    install -d ${DEPLOYDIR}/shim-unsigned
    install -m 0644 ${B}/shimx64.efi ${B}/mmx64.efi ${B}/fbx64.efi ${DEPLOYDIR}/shim-unsigned/
}
addtask deploy after do_install before do_build

B = "${S}"

FILES:${PN} = "${datadir}/shim"
# EFI PE images, not ELF: nothing to strip or split.
INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"
