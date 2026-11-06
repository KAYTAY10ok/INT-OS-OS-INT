# Shared desktop profile. Include only from the separate desktop build directory.
DISTRO_FEATURES:append = " wayland opengl"
# Foot needs a UTF-8 locale; generate only the initial desktop fallback.
GLIBC_GENERATE_LOCALES:pn-glibc-locale = "en_US.UTF-8"

# The unversioned upstream recipes follow development branches at this layer pin.
PREFERRED_VERSION_sway-1.11 = "1.11"
PREFERRED_VERSION_wlroots-0.19 = "0.19.3"
PACKAGECONFIG:append:pn-sway-1.11 = " swaybar swaynag"
PACKAGECONFIG:remove:pn-sway-1.11 = "default-wallpaper gdk-pixbuf"
PACKAGECONFIG:append:pn-wlroots-0.19 = " gbm"

# QEMU prototype: Mesa keeps its supported EGL/GLES/GBM, Wayland, Gallium,
# virtio/virgl and unconditional softpipe path. This does not qualify real GPUs.
PACKAGECONFIG:remove:pn-mesa:qemux86-64 = "intel amd nouveau svga libclc gallium-llvm"
# The supported nanosvg backend avoids bringing librsvg/Rust into this prototype.
PACKAGECONFIG:remove:pn-fuzzel = "librsvg"

# Use the existing PAM/logind session for seat access. Do not grant permanent raw
# input/video groups or run a second active seat broker.
SYSTEMD_AUTO_ENABLE:pn-seatd = "disable"
PACKAGECONFIG:remove:pn-seatd = "libseat-builtin"

# Keep desktop module packages distinct from the preserved console-core ABI.
LINUX_VERSION_EXTENSION:pn-linux-yocto = "-int-desktop1"
PR:pn-linux-yocto = "r2"
