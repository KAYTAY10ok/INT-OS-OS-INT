require int-image-minimal.bb

SUMMARY = "Experimental INT package-management image for QEMU"
DESCRIPTION = "Disposable QEMU-only signed-feed laboratory: RPM, DNF and a oneshot test service that runs one DNF case from a read-only fixture disk and powers off. Not an installation image."
COMPATIBLE_MACHINE = "^qemux86-64$"
IMAGE_FEATURES += "package-management"
# Test-only service; never add it to the console or desktop images.
IMAGE_INSTALL:append = " int-feed-smoke"
# DNF, Python and the RPM database need more room than the minimal image.
IMAGE_ROOTFS_EXTRA_SPACE = "262144"
