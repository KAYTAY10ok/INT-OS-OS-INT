# Disposable feed probe packages

`int-feed-probe` is a small test-only package in versions `1.0` and `2.0`.
It installs `/usr/share/int-feed-probe/version`, containing the package
version and a newline. The recipe defines no package scriptlets and requires
no runtime program. It is not installed in the existing images.

To build both versions later, first wait until all other INT operations have
finished. Open `./scripts/int --profile feed shell`, then run the following
inside that shell. Each `-R` file selects one version for that BitBake
invocation without changing the build configuration. Copy the first RPM
before building the second, because subsequent builds can alter deploy output.
The directory printed at the end contains separate unsigned copies for the
laboratory; retain it only as long as needed.

```sh
(
set -e
lab=$(mktemp -d /work/int-feed-probe.XXXXXX)
printf 'Probe copies: %s\n' "$lab"
printf 'PREFERRED_VERSION_int-feed-probe = "1.0"\n' > "$lab/v1.conf"
printf 'PREFERRED_VERSION_int-feed-probe = "2.0"\n' > "$lab/v2.conf"
bitbake -R "$lab/v1.conf" int-feed-probe
cp tmp/deploy/rpm/noarch/int-feed-probe-1.0-r0.noarch.rpm "$lab/"
bitbake -R "$lab/v2.conf" int-feed-probe
cp tmp/deploy/rpm/noarch/int-feed-probe-2.0-r0.noarch.rpm "$lab/"
)
```

These recipes and commands have not yet been built or exercised in the guest.
They provide fixtures only: they do not create a signed repository, validate
signatures, test an update or establish a recovery mechanism. Sign only
separate laboratory copies, never the deploy artifacts.
