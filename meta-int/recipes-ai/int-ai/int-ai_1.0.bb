SUMMARY = "INT local AI super command: one request, one checked system action"
DESCRIPTION = "int-ai turns a short French or English request into one action from a strict \
registry, validates it, asks for confirmation for any change and runs it without a shell. \
int-ai-model downloads a pinned, SHA-256 verified Qwen2.5 Instruct GGUF model and int-ai.service \
serves it with llama-server on 127.0.0.1 as the unprivileged int-ai user."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://int-ai file://int-ai-model file://int-ai.service file://int-ai-setup.service"
S = "${UNPACKDIR}"

inherit allarch systemd useradd

PACKAGES =+ "${PN}-setup"

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --home-dir ${localstatedir}/lib/int-ai --no-create-home \
                       --shell ${base_sbindir}/nologin --user-group int-ai"

# The model server stays disabled until a model is installed and chosen.
SYSTEMD_SERVICE:${PN} = "int-ai.service"
SYSTEMD_AUTO_ENABLE:${PN} = "disable"
# First-boot model download: a no-op unless the installer recorded INT_AI_MODEL.
SYSTEMD_PACKAGES = "${PN} ${PN}-setup"
SYSTEMD_SERVICE:${PN}-setup = "int-ai-setup.service"
SYSTEMD_AUTO_ENABLE:${PN}-setup = "enable"

do_install() {
    install -Dm0755 ${S}/int-ai ${D}${bindir}/int-ai
    install -Dm0755 ${S}/int-ai-model ${D}${bindir}/int-ai-model
    install -Dm0644 ${S}/int-ai.service ${D}${systemd_system_unitdir}/int-ai.service
    install -Dm0644 ${S}/int-ai-setup.service ${D}${systemd_system_unitdir}/int-ai-setup.service
    install -d -m0755 ${D}${localstatedir}/lib/int-ai ${D}${localstatedir}/lib/int-ai/models
}

FILES:${PN} += "${localstatedir}/lib/int-ai"
FILES:${PN}-setup = "${systemd_system_unitdir}/int-ai-setup.service"

RDEPENDS:${PN} = "python3-core python3-json python3-netclient python3-crypt python3-io"
# The rules engine works without a model; llama-server is needed only by int-ai.service.
RRECOMMENDS:${PN} = "llama-cpp"
RDEPENDS:${PN}-setup = "${PN}"
