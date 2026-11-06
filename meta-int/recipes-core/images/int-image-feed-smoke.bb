require int-image-minimal.bb

SUMMARY = "Experimental INT package-management image for QEMU"
DESCRIPTION = "Disposable feed laboratory base with RPM and DNF; no automated feed checks are included. Not an installation image."
COMPATIBLE_MACHINE = "^qemux86-64$"
IMAGE_FEATURES += "package-management"
