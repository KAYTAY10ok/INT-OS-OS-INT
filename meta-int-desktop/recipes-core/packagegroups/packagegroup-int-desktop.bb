SUMMARY = "Shared INT desktop applications and session configuration"
LICENSE = "MIT"
# RPM renames dbus by architecture; select the image machine before inheritance.
PACKAGE_ARCH = "${MACHINE_ARCH}"
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
