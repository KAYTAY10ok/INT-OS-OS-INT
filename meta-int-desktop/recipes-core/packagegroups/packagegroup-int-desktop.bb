SUMMARY = "Shared INT desktop applications and session configuration"
LICENSE = "MIT"
inherit packagegroup
RDEPENDS:${PN} = " \
    int-desktop-config \
    sway-1.11 \
    foot \
    fuzzel \
    dbus \
    ttf-dejavu-sans-mono \
    xkeyboard-config \
    libx11-compose-data \
    ncurses-terminfo \
"
