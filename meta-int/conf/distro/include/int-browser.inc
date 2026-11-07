# OS-INT browser profile. Include only from build-browser, after
# int-desktop.inc and int-live.inc. It keeps the validated profiles untouched.
#
# meta-browser/meta-firefox (wrynose) builds with OE-Core's own clang and Rust;
# meta-clang is not needed from whinlatter on (see docs/development/browser.md).

# ESR: one major line per year and a stable enterprise-policy schema.
PREFERRED_VERSION_firefox = "140%"
PREFERRED_VERSION_firefox-l10n-fr = "140%"
PREFERRED_VERSION_firefox-l10n-de = "140%"

# The shared desktop already provides the features Firefox needs here
# (int-desktop.inc: "wayland opengl"). INT has no X11, so build the GTK
# Wayland-only toolkit instead of the default X11+Wayland one.
# Left out on purpose:
#   webrtc       - large, and a classic local-IP leak path for OSINT work
#   alsa         - INT has no "alsa" DISTRO_FEATURE (audio would need it
#                  or a PulseAudio/PipeWire server; not part of this cut)
#   gpu webgl openmax forbid-multiple-compositors - off upstream as well
# Kept: the default WASM sandbox for third-party libraries (RLBox/wasi-sdk).
# It costs build time (wasi-sdk builds its own LLVM) but is a security
# boundary; "disable-sandboxed-libraries" is deliberately not used.
PACKAGECONFIG:pn-firefox = "wayland wayland-only rust-simd"
