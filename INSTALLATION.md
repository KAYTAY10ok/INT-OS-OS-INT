# Installation status

There is no installer, live ISO, disk formatter or supported hardware installation
path yet. The first milestone boots a kernel and ext4 image in disposable QEMU
storage. Do not write these development outputs to a physical disk.

Evaluate Calamares integration after the core image and update model work. The
installer must show the exact disk and planned changes, obtain explicit final
formatting confirmation, configure accounts/keyboard/timezone/bootloader/encryption,
retain logs without secrets and provide recovery. Test destructive paths only on
dedicated disposable virtual disks before considering real hardware.
