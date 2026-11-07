SUMMARY = "OS-INT cyber/opsec command-line tools"
DESCRIPTION = "Network analysis, privacy and encryption tools for the OS-INT edition. No service is enabled by this group: the Tor service is installed disabled."
LICENSE = "MIT"
inherit packagegroup
RDEPENDS:${PN} = " \
    nmap \
    tcpdump \
    tshark \
    wireguard-tools \
    openvpn \
    macchanger \
    netcat-openbsd \
    socat \
    traceroute \
    exiftool \
    gnupg \
    cryptsetup \
    tor \
    int-osint-hardening \
"
