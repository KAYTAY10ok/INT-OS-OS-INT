require recipes-core/images/int-image-core.bb
SUMMARY = "Shared INT desktop development image"
DESCRIPTION = "First-owner console core with one shared Sway desktop for INT-OS and OS-INT."
IMAGE_INSTALL:append = " packagegroup-int-desktop"
