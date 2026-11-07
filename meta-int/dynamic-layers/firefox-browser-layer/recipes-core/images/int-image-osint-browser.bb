# Relative to this file: the live image is itself a dynamic-layer recipe.
require ../../../int-desktop/recipes-core/images/int-image-live.bb

SUMMARY = "INT Linux OS-INT live/installer ISO with a hardened Firefox"
DESCRIPTION = "int-image-live plus Firefox ESR (meta-browser) and the INT enterprise policies. Build with --profile browser."

IMAGE_INSTALL:append = " \
    firefox \
    firefox-l10n-fr \
    firefox-l10n-de \
    int-firefox-policies \
"
