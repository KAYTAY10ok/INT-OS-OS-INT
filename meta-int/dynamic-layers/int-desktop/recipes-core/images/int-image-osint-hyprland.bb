# Relative to this file (dynamic-layer recipe, parsed only with meta-int-desktop).
require int-image-live.bb

SUMMARY = "INT Linux OS-INT live/installer ISO with the Hyprland session"
DESCRIPTION = "int-image-live plus Hyprland (blur, rounded corners, animations) as the OS-INT default session. Its dependency chain builds Rust and LLVM: build it on a machine with 150+ GB free (e.g. WSL2), with --profile live."

IMAGE_INSTALL:append = " hyprland"
# Without Hyprland's Qt-based helper tools.
BAD_RECOMMENDATIONS += "hyprland-guiutils hyprshutdown hyprland-contrib"
