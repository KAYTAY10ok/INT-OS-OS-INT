require int-image-minimal.bb
SUMMARY = "Disposable INT Linux boot verification image"
DESCRIPTION = "QEMU-only test image that runs assertions on boot and powers off. Not an installation image."
COMPATIBLE_MACHINE = "^qemux86-64$"
IMAGE_INSTALL:append = " int-boot-smoke glibc-utils"
