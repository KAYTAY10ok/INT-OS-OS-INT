# Disposable feed probe packages

`int-feed-probe` is a small test-only package in versions `1.0` and `2.0`.
It installs `/usr/share/int-feed-probe/version`, containing the package
version and a newline. The recipe defines no package scriptlets and requires
no runtime program. It is not installed in the existing images.

Both versions have been built with BitBake; the retained console log is
`/workspace/int-linux-work/build-feed-probes.log` and the copied RPMs are under
`/workspace/int-linux-work/int-feed-probe.5Byp1F/`. They were used in the
[isolated fixture generator test](validation-feed-fixtures-2026-11-06.md),
but have not yet been installed or updated in the guest.

To rebuild both versions, first wait until all other INT operations have
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

These recipes provide fixtures only: they do not themselves create a signed
repository, validate signatures, test an update or establish a recovery mechanism. Sign only
separate laboratory copies, never the deploy artifacts.
