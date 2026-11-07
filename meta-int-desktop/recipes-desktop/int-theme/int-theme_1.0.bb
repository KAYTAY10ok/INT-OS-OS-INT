SUMMARY = "INT desktop themes: presets, generated wallpapers, INT ASCII logo and the int-theme command"
DESCRIPTION = "int-theme list|current|set|wallpaper|ensure. Presets dark, light, blue, pink, anime for Sway (and Hyprland snippets). Wallpapers are original procedural art generated at build time."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://int-theme file://int-dashboard file://int-wallpaper-gen file://int.txt file://int-fetch.sh \
           file://themes/dark.theme file://themes/light.theme file://themes/blue.theme \
           file://themes/pink.theme file://themes/anime.theme"
S = "${UNPACKDIR}"
inherit allarch python3native

do_compile() {
    ${PYTHON} ${S}/int-wallpaper-gen ${S}/themes ${B}/wallpapers 1920 1080
}

do_install() {
    install -Dm0755 ${S}/int-theme ${D}${bindir}/int-theme
    install -Dm0755 ${S}/int-dashboard ${D}${bindir}/int-dashboard
    install -d ${D}${datadir}/int/themes ${D}${datadir}/int/wallpapers
    install -m0644 ${S}/themes/*.theme ${D}${datadir}/int/themes/
    install -m0644 ${B}/wallpapers/*.png ${D}${datadir}/int/wallpapers/
    install -Dm0644 ${S}/int.txt ${D}${datadir}/int/ascii/int.txt
    install -Dm0644 ${S}/int-fetch.sh ${D}${sysconfdir}/profile.d/int-fetch.sh
}

FILES:${PN} = "${bindir}/int-theme ${bindir}/int-dashboard ${datadir}/int ${sysconfdir}/profile.d/int-fetch.sh"
RDEPENDS:${PN} = "python3-core python3-json python3-shell fastfetch swaybg"
