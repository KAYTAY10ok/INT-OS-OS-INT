require recipes-core/images/int-image-desktop.bb
SUMMARY = "Disposable VM for the shared INT desktop"
IMAGE_INSTALL:append = " int-core-smoke int-desktop-smoke"
