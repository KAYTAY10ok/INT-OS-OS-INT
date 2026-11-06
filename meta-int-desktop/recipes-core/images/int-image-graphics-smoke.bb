require recipes-core/images/int-image-desktop-smoke.bb
SUMMARY = "Disposable VM for INT graphical console verification"
IMAGE_INSTALL:append = " int-graphics-smoke"
