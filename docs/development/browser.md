# OS-INT browser: Firefox from meta-browser

Status: **not built.** No BitBake parse or build of the `browser` profile has
run yet. Everything below is source-level work and estimates. The first real
build must happen on a large machine (WSL2 or a big Linux host), not in a
cloud session.

## What was added

| Piece | Path |
| --- | --- |
| Pinned layer source | `configs/sources.lock.json` → `meta-browser` |
| Build profile | `scripts/int --profile browser` → `$INT_WORKDIR/build-browser` |
| Profile configuration | `meta-int/conf/distro/include/int-browser.inc` |
| Firefox enterprise policies | `meta-int/recipes-browser/int-firefox-policies/` |
| Image | `meta-int/dynamic-layers/firefox-browser-layer/recipes-core/images/int-image-osint-browser.bb` |

`int-image-osint-browser` is `int-image-live` plus `firefox`, the French and
German language packs and `int-firefox-policies`. `int-image-live` itself is
unchanged. The image is in a `BBFILES_DYNAMIC` directory of `meta-int`. Only
a build that includes `meta-firefox` parses it, so the other profiles don't
need the Firefox layer.

## Pinned layers and compatibility

| Layer | Repository | Revision | Why it fits |
| --- | --- | --- | --- |
| `meta-browser/meta-firefox` | `https://github.com/OSSystems/meta-browser` | `0715454e29ac38fb0a25bdbb1e0e26fdc4dc7ae3` (head of branch `wrynose`, 2026-10-01) | `LAYERSERIES_COMPAT_firefox-browser-layer = "kirkstone scarthgap whinlatter wrynose"`; `LAYERDEPENDS = "core openembedded-layer"` |

`meta-firefox` depends on `clang-layer` only when the series is not
`whinlatter` or `wrynose`:
`LAYERDEPENDS:append = '${@bb.utils.contains_any("LAYERSERIES_CORENAMES", "whinlatter wrynose", "", " clang-layer", d)}'`.
Its README says the same: it needs meta-clang only before Whinlatter. The
pinned OE-Core (`ae5a3010…`, `LAYERSERIES_CORENAMES = "wrynose"`) has its own
toolchain, and that toolchain covers everything the recipes need:

- clang/LLVM 22.1.8 (`meta/recipes-devtools/clang`). The recipe uses
  `TOOLCHAIN:pn-firefox = "clang"` and `clang-native`. Firefox 144+ needs
  Clang ≥ 17, and wasi-sdk needs ≥ 18.
- Rust/Cargo 1.94.1. Firefox needs ≥ 1.82, and upstream tests master with
  1.94.0.
- nasm, pulseaudio, gtk+3, dbus-glib, libevent, libva and pciutils (`libpci`)
  are in OE-Core.
- `nodejs-native` (22.23.3) is in the pinned `meta-oe`. `meta-firefox`
  provides its own `cbindgen`, `python3-zstandard`, `wasi-sdk`, `wasm-tools`
  and `wasm-component-ld`. It has layer priority 7, so its `cbindgen` and
  `python3-zstandard` win over the `meta-oe`/`meta-python` copies.

So no extra layer is needed: **no meta-clang, no meta-rust, no
meta-lts-mixins.** meta-clang does have a `wrynose` branch
(`ef0d22f21910a0c30c967eeb17d8f209806e2d81`), but it is not pinned because
nothing requires it. `meta-chromium` (the other sub-layer) is not used.

Upstream CI (`OldManYellsAtCloud/meta-firefox-test`, `kas/repos/wrynose.yml`)
tests wrynose with OE-Core `6f5681af…`, meta-oe `d97b5602…` and bitbake
`acfe02fa…`, and an X11+Wayland distro. INT's pins differ. Their extra
`PACKAGECONFIG:remove:pn-mesa = "libclc"` is already in `int-desktop.inc` for
qemux86-64. Their meta-oe nodejs patch only saves sstate. These are
**compatibility arguments, not a build result.**

## Configuration choices (`int-browser.inc`)

- `PREFERRED_VERSION_firefox = "140%"`: ESR 140.10.2esr. The branch also has
  150.0.3. ESR keeps one policy schema per year.
- `PACKAGECONFIG:pn-firefox = "wayland wayland-only rust-simd"`. INT has no
  `x11` DISTRO_FEATURE, so the GTK toolkit is built Wayland-only. The
  Wayland and OpenGL features come from `int-desktop.inc`, and no new
  DISTRO_FEATURE is added.
- Left out: `webrtc` (large, and a local-IP leak path), `alsa` (not a
  DISTRO_FEATURE here), and `gpu`/`webgl`/`openmax` (also off upstream).
- Kept: the WASM library sandbox (wasi-sdk). It is the heaviest optional
  part, but it is a security boundary. `disable-sandboxed-libraries` would
  save time at the cost of that boundary, so it is not set.

The profile order is `int-desktop.inc`, `int-live.inc`, `int-browser.inc`.
`int-live.inc` is required because the image is built on `int-image-live`,
which needs its EFI, installer initramfs and `-int-live1` kernel settings.
The layer order is the desktop layers followed by
`/work/sources/meta-browser/meta-firefox`.

## Firefox policies

`/etc/firefox/policies/policies.json`, root-owned and mode 0644:

- Telemetry, studies, app updates and feedback commands are disabled. The
  updater is also left out of the build by the upstream mozconfig, and INT's
  signed feed delivers updates.
- DNS-over-HTTPS is off by default and **not locked**, so the user can turn
  it on.
- Tracking protection uses the `strict` category, which needs ESR ≥ 140.2.
  It is not locked: in strict mode some sites break, and the user can add
  exceptions.
- `OfferToSaveLoginsDefault: false`: no password-saving prompt by default,
  and the password manager stays available.
- Address and card autofill, search suggestions, Firefox Suggest, network
  prediction, captive-portal and connectivity checks, sponsored content,
  recommendations, generative AI, DRM (EME) and OpenH264 downloads are off by
  default.
- HTTPS-Only mode is on by default, and the user can turn it off.
- Extensions: nothing is installed or downloaded automatically. **uBlock
  Origin is only allowed, never fetched.** The user installs it themselves.
  Only policies documented by Mozilla `policy-templates` for ESR 140 are
  used.

These policies do not make the browser anonymous. See `THREAT_MODEL.md`.

## Build commands (WSL2)

Prepare WSL2 as in `docs/COMPILER-SOUS-WINDOWS.md`, then from the checkout:

```bash
./scripts/int bootstrap                      # also fetches sources/meta-browser at the pinned SHA
./scripts/int builder
./scripts/int --profile browser configure
./scripts/int --profile browser build        # = bitbake int-image-osint-browser
```

The ISO lands in
`$INT_WORKDIR/build-browser/tmp/deploy/images/qemux86-64/int-image-osint-browser-qemux86-64.rootfs-*.iso`.
`$INT_WORKDIR` defaults to `../int-linux-work`.

Firefox alone can be built first to surface toolchain problems sooner:

```bash
./scripts/int --profile browser build firefox
```

The generated `local.conf` keeps `BB_NUMBER_THREADS = "4"` and
`PARALLEL_MAKE = "-j4"`. A larger machine can raise them in
`$INT_WORKDIR/build-browser/conf/int-local.conf`. If WSL2 has less than
~32 GB of RAM, keep `PARALLEL_MAKE` low so that linking `libxul` and the
LLVM builds don't run out of memory.

`./scripts/int --profile browser check` is not supported:
`scripts/check-config.py` only knows `core`, `desktop` and `feed`, the same
as for `live`.

## Expected cost (estimates, not measured)

These numbers are **estimates** from typical Firefox/LLVM builds under
Yocto. INT has not measured them.

- **Disk:** about 60–120 GB more than an existing `build-live`. That covers
  the Firefox source and objects, the native clang/LLVM, wasi-sdk (its own
  LLVM checkout), Rust crates and the sstate. `rm_work` is on. With no
  existing caches, plan for 200 GB or more of free space in total.
- **RAM:** 16 GB is the practical minimum with `-j4`. 32 GB or more is
  recommended.
- **Time:** reusing the `live` sstate, about 3–6 h on 8 cores and 32 GB, or
  6–12 h or more on 4 cores and 16 GB. From an empty cache, add the full
  live-image time.
- **Downloads:** several GB (the Firefox source tarball is about 600 MB,
  plus wasi-sdk with its submodules, crates and l10n `.xpi` files).

## Known risks before the first build

- `wayland-only` is not part of upstream's wrynose CI matrix. Upstream uses
  an X11+Wayland distro. If configure fails on toolkit selection, look there
  first.
- Upstream builds Firefox with `--enable-official-branding`. Redistributing
  an ISO that contains Mozilla's official branding raises a trademark
  question, and it must be checked before any public release.
- There is no audio without an `alsa` DISTRO_FEATURE or a running
  PulseAudio/PipeWire server.
- QEMU validation of the browser image (start Firefox, check
  `about:policies`) is still to be written.
