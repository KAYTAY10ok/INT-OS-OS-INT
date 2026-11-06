require int-image-minimal.bb

SUMMARY = "Experimental INT package-management image for QEMU"
DESCRIPTION = "Disposable QEMU-only local feed experiment. Not an installation image."
COMPATIBLE_MACHINE = "^qemux86-64$"
IMAGE_FEATURES += "package-management"
IMAGE_INSTALL:append = " int-feed-smoke"
