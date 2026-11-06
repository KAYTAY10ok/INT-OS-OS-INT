FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://int-baseline.cfg"
# This configuration adds a core firewall ABI; keep modules distinct from the
# preserved foundation kernel rather than silently sharing its uname suffix.
LINUX_VERSION_EXTENSION = "-int-core1"
PR = "r1"
