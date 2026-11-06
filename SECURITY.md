# Security status

This is a development foundation, not a security-qualified distribution. Review
`THREAT_MODEL.md` for assets, boundaries and residual risks. There are no supported
releases or configured public vulnerability-reporting channel yet.

Keep TLS, source checksums, package signatures and artifact verification enabled.
The build mounts public CA trust; it must never copy proxy credentials into the
repository or image. Target root is locked by default. No default shared password,
SSH server, telemetry service, security scanner or external guest probe is added.

The core image enrolls its first owner through the trusted local console using
upstream passwd/PAM. Enrollment records have root-only access; activation follows
a durable commit. Wheel sudo requires a fresh password and PAM has no empty-password
exception. Default nftables input/forward policy is drop, output is accept.
Networkd requires successful firewall activation; service stop retains the rules.
The [core VM test](docs/development/validation-core-2026-11-05.md) verifies IPv4
packet controls, missing/invalid policy startup failure, recovery, and real login
and sudo, including rejection of an incorrect password.

Boot/core smoke services and their privileged test helpers belong only to their
respective disposable smoke images. `int-image-core` excludes them. These tests
do not qualify IPv6 filtering, full privacy/lab isolation, AppArmor, encryption,
secure boot, signed updates, physical hardware or repeated power-loss recovery.

The kernel pin is behind the latest upstream 6.18 patch level observed during
research. Review vulnerabilities and update the coherent OE/kernel snapshot before
release. Do not publish unsigned development RPMs as a trusted INT feed.
