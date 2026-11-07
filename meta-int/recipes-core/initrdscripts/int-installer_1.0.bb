SUMMARY = "INT Linux French/English UEFI disk installer (initramfs-framework module)"
DESCRIPTION = "Replaces the OE install-efi module: language, keyboard and edition choice, numbered disk selection with double confirmation, GPT layout, GRUB and a firmware boot entry."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-install-efi.sh"
S = "${UNPACKDIR}"
inherit allarch
RDEPENDS:${PN} = "initramfs-framework-base parted e2fsprogs-mke2fs dosfstools util-linux-blkid util-linux-mkswap efibootmgr ${VIRTUAL-RUNTIME_base-utils}"
# Same entry point as OE's module: setup-live runs /init.d/<LABEL>.sh.
RCONFLICTS:${PN} = "initramfs-module-install-efi"
do_install() {
    install -Dm0755 ${S}/int-install-efi.sh ${D}/init.d/install-efi.sh
}
FILES:${PN} = "/init.d/install-efi.sh"
