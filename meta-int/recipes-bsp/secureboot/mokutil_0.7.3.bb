SUMMARY = "Manage shim Machine Owner Keys (MOK) from Linux"
DESCRIPTION = "mokutil queues MOK enrollment, deletion and Secure Boot state \
changes for shim's MokManager and reports the Secure Boot state. INT uses it \
to request enrollment of the INT owner certificate. Not yet installed in any \
image; see docs/development/secure-boot.md."
HOMEPAGE = "https://github.com/lcp/mokutil"
SECTION = "bootloaders"
LICENSE = "GPL-3.0-or-later"
LIC_FILES_CHKSUM = "file://COPYING;md5=d32239bcb673463ab874e80d47fae504"

# Upstream tag 0.7.3 (lightweight) points at this commit; the fetcher checks it.
SRC_URI = "git://github.com/lcp/mokutil.git;protocol=https;nobranch=1;tag=${PV}"
SRCREV = "9ddb02fd2e3f5a2cc4dc3b4eacfe2f099916f548"

DEPENDS = "openssl efivar keyutils virtual/crypt"

inherit autotools pkgconfig

COMPATIBLE_HOST = "(i.86|x86_64|arm|aarch64|riscv64).*-linux"

EXTRA_OECONF = "--with-bash-completion-dir=${datadir}/bash-completion/completions"

FILES:${PN} += "${datadir}/bash-completion"

RRECOMMENDS:${PN} = "kernel-module-efivarfs"
