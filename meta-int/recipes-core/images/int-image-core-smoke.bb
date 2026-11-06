require int-image-core.bb
SUMMARY = "Disposable VM for INT account and firewall verification"
IMAGE_INSTALL:append = " int-core-smoke"
