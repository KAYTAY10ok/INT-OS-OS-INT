# Shared desktop integration plan

Status: researched on 2026-11-05 UTC; **not integrated, parsed, built or booted**.
The console/account/firewall milestone remains the priority. This document does
not change source locks, layers, distro features, recipes, kernel configuration,
or the shared Sway/Wayland desktop decision.

## Available foundation

The existing locked OE-Core revision
`ae5a301091f5b0574ea7444aab40b309b6d9f3f2` provides:

| Component | Recipe/version | Relevant purpose |
| --- | --- | --- |
| Wayland | `recipes-graphics/wayland/wayland_1.24.0.bb` | Client/server libraries and native scanner |
| Protocols | `recipes-graphics/wayland/wayland-protocols_1.47.bb` | Protocol XML |
| Mesa | `recipes-graphics/mesa/mesa.bb`, `mesa.inc`, 26.0.5 | EGL/GLES/GBM and software/virtio rendering |
| libdrm | `recipes-graphics/drm/libdrm_2.4.131.bb` | DRM userspace |
| libinput | `recipes-graphics/wayland/libinput_1.30.2.bb` | Input, with pinned downstream security patches |
| libxkbcommon | `recipes-graphics/xorg-lib/libxkbcommon_1.13.1.bb` | Keymap compilation |
| Keyboard data | `recipes-graphics/xorg-lib/xkeyboard-config_2.47.bb` | Required keymap files, also used on Wayland |
| pixman | `recipes-graphics/xorg-lib/pixman_0.46.4.bb` | CPU rendering |
| seatd/libseat | `recipes-core/seatd/seatd_0.9.3.bb` | Seat access; logind backend enabled with systemd |
| Display information | `recipes-support/libdisplay-info/libdisplay-info_0.3.0.bb` | wlroots dependency |
| Hardware data | `recipes-support/hwdata/hwdata_0.406.bb` | Native wlroots build dependency |
| Diagnostic client | `recipes-graphics/wayland/wayland-utils_1.3.0.bb` | `wayland-info` |

Pango 1.57.0, Cairo 1.18.4, fontconfig 2.17.1, JSON-C 0.18 and D-Bus
1.16.2 are already represented by OE-Core recipes. The existing pinned
meta-openembedded layer provides `ttf-dejavu_2.37.bb`.

Neither existing source tree contains recipes for Sway, wlroots, foot, fcft,
tllist, fuzzel, Waybar, or the Mako notification daemon. The unrelated
`python3-mako` recipe is a Python template engine, not that daemon.

## Candidate maintained layer and exact selection

The official upstream layer is <https://codeberg.org/flk/meta-wayland>.
Its `wrynose` branch pointed to
`2b97daa23e0e612a087ea54b150bd0b8e0ff9378` when inspected. At that exact
revision, `conf/layer.conf` declares `LAYERSERIES_COMPAT_wayland = "wrynose"`
and depends on `core` and `openembedded-layer`, already present in INT's
layer set. This compatibility declaration is not a substitute for an actual
BitBake parse and dependency/build verification.

Official API evidence, read over verified HTTPS:

- [Branch list](https://codeberg.org/api/v1/repos/flk/meta-wayland/branches?limit=50)
- [Complete pinned tree](https://codeberg.org/api/v1/repos/flk/meta-wayland/git/trees/2b97daa23e0e612a087ea54b150bd0b8e0ff9378?recursive=true)
- [Pinned layer configuration](https://codeberg.org/api/v1/repos/flk/meta-wayland/contents/conf/layer.conf?ref=2b97daa23e0e612a087ea54b150bd0b8e0ff9378)

For any recipe below, its exact source is available through
`https://codeberg.org/api/v1/repos/flk/meta-wayland/contents/<recipe-path>?ref=2b97daa23e0e612a087ea54b150bd0b8e0ff9378`.
The API tree reported `truncated: false`. No archive was imported or layer
added during this research.

| Candidate | Exact recipe path | Pinned application source revision |
| --- | --- | --- |
| Sway stable 1.11 | `recipes-wlroots/sway/sway-1.11_1.11.bb` | `990b23c0e584114c3694447344d6bbf44b2d748f` |
| wlroots stable 0.19.3 | `recipes-wlroots/wlroots/wlroots-0.19_0.19.3.bb` | `88a869855742281c98c22cab9641b317b8d065ef` |
| foot 1.26.1 | `recipes-support/foot/foot_1.26.1.bb` | `ef15414b301513a75193fd872de79d6379f41a79` |
| fcft 3.3.3 | `recipes-extended/fcft/fcft_3.3.3.bb` | `38de2ae450df667ac71ba4811fe535aa1954a217` |
| fuzzel 1.14.1 | `recipes-support/fuzzel/fuzzel_1.14.1.bb` | `450cc9f5e1980a0da79955703ac33043e5628a86` |
| Mako 1.10.0 | `recipes-support/mako/mako_1.10.0.bb` | `b131bc143f6b0f24d650f16bb88a11c7cb011c20` |
| Waybar 0.15.0 | `recipes-gtk/waybar/waybar_0.15.0.bb` | `90b209add8937514d0a987aa842e701bd8f1232e` |

The layer also supplies `recipes-extended/tllist/tllist_1.1.0.bb`.

**Select package/recipe `sway-1.11`, not `sway`.** At the inspected layer pin,
`sway` is 1.13-dev and depends on unversioned development `wlroots` 0.21-dev.
The stable recipe explicitly depends on `wlroots-0.19`. Installing `sway-1.11`
and explicitly preferring 1.11 / 0.19.3 for their versioned recipe names avoids
accidentally selecting those development recipes. Do not install multiple Sway
branches together: their installed executable/configuration paths can overlap.
The layer's Sway 1.12 recipe is an RC at this pin, not the stable choice here.

Candidate version selectors for that future profile, **not applied**:

```bitbake
PREFERRED_VERSION_sway-1.11 = "1.11"
PREFERRED_VERSION_wlroots-0.19 = "0.19.3"
PACKAGECONFIG:append:pn-sway-1.11 = " swaybar swaynag"
```

Those selectors do not redirect an `IMAGE_INSTALL` entry named `sway` to the
versioned package. The package group itself must request `sway-1.11`.

## Smallest useful shared desktop

Start with one package group shared by both editions:

- Stable `sway-1.11`, enabling its `swaybar` and `swaynag` PACKAGECONFIG options.
  Those two options are absent from this recipe's defaults, so the bar must be
  enabled deliberately. Keep the initial theme and shortcuts in configuration.
- `foot` as the terminal, `fuzzel` as the launcher, one DejaVu monospace font,
  `xkeyboard-config`, compose data and suitable terminfo. Verify actual runtime
  package names/files from package manifests instead of relying on recommends.
- A D-Bus user session; the `dbus` package owns `dbus-run-session` in this
  OE-Core pin. Add Mako once the terminal/launcher/session tests pass.
- `wayland-utils` and Sway IPC for test evidence. Add screenshots/tools to the
  disposable desktop test image rather than expanding the production group
  solely to support tests.

Sway's upstream layer recipe also has runtime dependencies `swaybg python3
python-i3ipc` and recommends foot/jq/grim/slurp/wl-clipboard/sway-contrib.
`python-i3ipc` is a real layer recipe using Python 3, despite its name. Account
for these in size measurements; do not claim the recipe is Python-free. Avoid
removing dependencies before establishing why upstream configured them.

Swaybar can cover the first status bar without adding a second bar stack.
Waybar is available later but requires `gobject-introspection-data` in distro
features, plus GTK3, gtkmm3, gtk-layer-shell, GObject introspection, jsoncpp,
fmt and spdlog. Its default modules also pull in networking/input/MPRIS/UPower
support. That is a measurable expansion, not a prerequisite for first Sway boot.

Fuzzel defaults enable `png` and `librsvg`; the latter adds Cairo/librsvg and its
Rust build dependency. Its recipe explicitly supports disabling that option
and using the nanosvg backend. Evaluate that supported option for the initial
image, then test SVG/icon behavior. Foot/fcft have their own font shaping
dependencies (fontconfig, freetype, harfbuzz, pixman, utf8proc and tllist).

## Renderer and build-cost choices

The current INT distro feature list has neither `wayland` nor `opengl`.
The proposed desktop configuration must deliberately enable the required
features and retain the console image as a separate tested artifact. No such
change is made here. Sway's recipe has an unconditional build dependency on
`virtual/libgles2`, even for an initial runtime Pixman test.

Adding `opengl` on x86-64 activates significant defaults in `mesa.bb`:
`libclc gallium-llvm intel amd nouveau svga`, in addition to EGL/GLES/GBM,
Gallium and virtio support. `gallium-llvm` depends on both `llvm` and
`llvm-native`; `libclc` brings `mesa-tools-native`. A full driver build can
consume substantially more time/storage than the current console milestone.
No measured desktop build budget is available yet.

For a dedicated QEMU prototype, evaluate a scoped Mesa PACKAGECONFIG that
retains EGL/GLES/GBM, Wayland, Gallium and virtio while excluding unrelated
GPU drivers, `libclc` and `gallium-llvm`. The pinned `mesa.inc` unconditionally
includes the Gallium softpipe driver; `virtio` adds virgl, while llvmpipe is
added only with `gallium-llvm`. Thus softpipe/Pixman are realistic software
alternatives, without claiming llvmpipe is available in a build without LLVM.
Verify Meson dependency resolution and actual renderers before adopting an
override. This QEMU profile would not qualify physical Intel/AMD/NVIDIA GPUs.

Use `WLR_RENDERER=pixman` for the first headless compositor test. Keep a later
EGL/GBM test separate so a successful CPU renderer cannot hide a broken GL
stack. Do not require host VirGL acceleration for the first virtual display.
Do not add X11, Xwayland, Vulkan or OpenCL merely to start this prototype.

## Session and device access

Run Sway as the enrolled unprivileged owner. The existing systemd configuration
enables logind and PAM; the pinned `libpam_1.7.2.bb` appends
`session optional pam_systemd.so` to `common-session` for systemd images.
Verify `XDG_RUNTIME_DIR` ownership/mode and the actual login session rather
than assuming that this build metadata proves runtime integration.

The pinned seatd recipe enables the libseat logind backend with systemd and
also installs a seatd daemon/unit. Choose one seat access path explicitly.
An initial real-VT login with logind avoids granting every owner permanent
raw `input` device access. Do not run the compositor as root or add broad
device permissions to make a failed session test pass. A serial login is
useful for headless automation but is not proof of an active graphical seat.

The current generated core kernel `.config`, inspected read-only during its
build, already has `CONFIG_DRM=y`, `CONFIG_DRM_VIRTIO_GPU=y`,
`CONFIG_INPUT_EVDEV=y`, `CONFIG_VT=y`, `CONFIG_VT_CONSOLE=y`,
`CONFIG_DRM_FBDEV_EMULATION=y` and `CONFIG_FRAMEBUFFER_CONSOLE=y`.
`CONFIG_VIRTIO_INPUT=m`; include its matching module in a test image if using
virtio keyboard/mouse devices. This is static configuration evidence only.
Re-audit the exact image/kernel pair used for each desktop test.

## Test sequence

1. Pin and bootstrap the candidate layer, review its recipes/appends, then run
   an actual metadata parse and dependency inspection. Build only the selected
   stable compositor/terminal/launcher path first. Keep one BitBake operation
   per work directory, and retain the known-good console artifacts.
2. Build a disposable desktop smoke image. After real owner login, launch
   Sway as that owner in a D-Bus session with `WLR_BACKENDS=headless`,
   `WLR_RENDERER=pixman`, and one requested headless output. Bound the run time
   and clean up only the compositor/test children created by that run.
3. Require a responsive Sway IPC socket, an active headless output, and
   `wayland-info` showing a functioning client connection. Open foot running a
   controlled test command, verify its UID remains unprivileged, and verify
   its mapped application node/geometry via IPC. Check the configured bar and
   terminal output; a socket file alone is not a successful desktop test.
4. Exercise actual launcher invocation/selection and notification delivery with
   controlled input or a dedicated test input tool. `fuzzel --version` or an
   installed binary does not validate a usable launcher. Retain logs and a
   captured rendered image where the capture path is itself verified.
5. Add a separate QEMU DRM/virtio display test with keyboard/mouse and a real
   VT session; verify output, input, focus, terminal shortcuts, launcher,
   session exit and a later EGL/GBM path. Preserve no host TCP forwarding and
   restricted guest networking. Use a private Unix socket if a viewer/control
   channel is needed, rather than opening an unauthenticated network service.
6. Measure image size, startup and idle resources only after functional tests
   are repeatable. Record renderer, CPU model, memory, image/kernel hashes and
   workload. Continue to physical hardware qualification separately.

Keep `DEFAULTTUNE="x86-64"` and the existing machine-flag checks. Audit new
graphics build commands and application CPU assumptions; passing a Pixman/QEMU
run is not proof that every renderer and client avoids mandatory AVX/AVX2.
No physical GPU, suspend, HiDPI, accessibility, keyboard layout, audio, battery,
screen lock or performance qualification is established by this research.
