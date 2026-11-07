SUMMARY = "Tor anonymity network client (OS-INT, localhost SOCKS only)"
DESCRIPTION = "Tor client built without the relay and directory authority \
modules, with a hardened default torrc that only listens on 127.0.0.1:9050. \
The systemd service is installed disabled; enable it with 'int-privacy tor on'."
HOMEPAGE = "https://www.torproject.org/"
SECTION = "net"

# Built without --enable-gpl, so tor itself stays under its 3-clause BSD
# licence; LICENSE lists the bundled components described in LICENSE. The
# GeoIP databases are CC-BY-SA-4.0 and live in their own package.
LICENSE = "BSD-3-Clause & BSD-2-Clause & MIT & ISC & CC-BY-SA-4.0"
LICENSE:${PN} = "BSD-3-Clause & BSD-2-Clause & MIT & ISC"
LICENSE:${PN}-geoip = "CC-BY-SA-4.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=1c49e60ec3ca90464faf1a4d6c19e384"

# Official release tarball. The checksum below matches the published
# tor-0.4.9.16.tar.gz.sha256sum file on dist.torproject.org (2026-11-07).
SRC_URI = "https://dist.torproject.org/${BP}.tar.gz \
           file://torrc \
           file://tor.service \
"
SRC_URI[sha256sum] = "6180e193152f4525bdca5475168419b2a2035b963c3c60162a187f86e6160e48"

UPSTREAM_CHECK_URI = "https://dist.torproject.org/"
UPSTREAM_CHECK_REGEX = "tor-(?P<pver>\d+(\.\d+)+)\.tar\.gz"

DEPENDS = "libevent openssl zlib libcap"

inherit autotools pkgconfig systemd useradd features_check

REQUIRED_DISTRO_FEATURES = "systemd"

PACKAGECONFIG ??= "lzma zstd systemd \
    ${@bb.utils.filter('DISTRO_FEATURES', 'seccomp', d)} \
"
PACKAGECONFIG[lzma] = "--enable-lzma,--disable-lzma,xz"
PACKAGECONFIG[zstd] = "--enable-zstd,--disable-zstd,zstd"
PACKAGECONFIG[systemd] = "--enable-systemd,--disable-systemd,systemd"
PACKAGECONFIG[seccomp] = "--enable-seccomp,--disable-seccomp,libseccomp"

# Client only: without the relay module tor cannot be configured as a relay,
# bridge, exit, directory cache or authority, whatever the torrc says.
EXTRA_OECONF = " \
    --disable-module-relay \
    --disable-module-dirauth \
    --disable-unittests \
    --disable-asciidoc \
    --disable-manpage \
    --disable-html-manual \
    --disable-libscrypt \
    --disable-zstd-advanced-apis \
    --disable-tool-name-check \
    --with-tor-user=tor \
    --with-tor-group=tor \
"

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --no-create-home --home-dir ${localstatedir}/lib/tor \
    --shell ${base_sbindir}/nologin --user-group tor"

# Installed but never enabled: no network service runs until the owner asks.
SYSTEMD_SERVICE:${PN} = "tor.service"
SYSTEMD_AUTO_ENABLE:${PN} = "disable"

do_install:append() {
    install -d -m 0755 ${D}${sysconfdir}/tor
    install -m 0644 ${UNPACKDIR}/torrc ${D}${sysconfdir}/tor/torrc
    # Upstream's sample enables nothing but would confuse the owner next to
    # the INT torrc; it stays in the source documentation.
    rm -f ${D}${sysconfdir}/tor/torrc.sample
    # torify only wraps torsocks, which has no pinned recipe yet.
    rm -f ${D}${bindir}/torify

    install -d ${D}${systemd_system_unitdir}
    sed -e 's|@BINDIR@|${bindir}|g' \
        -e 's|@SYSCONFDIR@|${sysconfdir}|g' \
        -e 's|@BASE_BINDIR@|${base_bindir}|g' \
        ${UNPACKDIR}/tor.service > ${D}${systemd_system_unitdir}/tor.service
    chmod 0644 ${D}${systemd_system_unitdir}/tor.service
}

PACKAGE_BEFORE_PN = "${PN}-geoip"
FILES:${PN}-geoip = "${datadir}/tor/geoip ${datadir}/tor/geoip6"
RRECOMMENDS:${PN} = "${PN}-geoip"

CONFFILES:${PN} = "${sysconfdir}/tor/torrc"
