# Opt-in: hardware OpenGL/Vulkan for real Intel and AMD PCs (iris, radeonsi,
# anv, radv, llvmpipe). Mesa then needs LLVM and libclc: plan tens of GB of
# build space (WSL2 or a large builder), not the small cloud session.
# Use from int-local.conf of the live build (after int-desktop.inc):
#   require conf/distro/include/int-gpu.inc
# Without it, Sway falls back to its CPU renderer on those GPUs (int-renderer).
INT_MESA_REMOVE = "nouveau svga"
