# Unsigned RPM rejection in QEMU — 2026-11-06 UTC

The experimental feed image rejected an unsigned version 2.0 RPM in a real
QEMU guest. Version 1.0 had first been installed from a valid signed local
repository. The version 2.0 repository metadata was freshly indexed and
signed, so the test reached package verification rather than failing on a
stale repository checksum. After DNF rejected the upgrade, the guest checked
that both the installed RPM version and version file still reported 1.0.

This validates one rejection path for the tested local fixtures and target
image. Wrong-key and modified RPMs, metadata failures, network updates and
interrupted transactions require separate tests. It is not a production feed
or release qualification.

## Inputs and evidence

The experimental image rebuild completed 3,963 tasks, of which 3,927 were
already up to date, without failure. The retained build log is
`/workspace/int-linux-work/build-image-feed-unsigned-20261106.log`, SHA-256
`a263be14eb656c20fb4502852f2b43481d4796de8fdde5401a54dc04d9f74da0`.
The kernel release was `6.18.54-int-core1`. The guest ran under QEMU 8.2.2
using TCG and `qemu64`, with the root filesystem on a temporary snapshot, a
separate read-only virtio fixture disk, and no network device.

The independently supplied disposable test-key fingerprint was
`D8F858DAF212985476049E82F0FD22E0B698895A`. It expires at
2026-11-07 13:19:05 UTC and is not production trust material. The disk used
the earlier isolated fixture set described in
[validation-feed-fixtures-2026-11-06.md](validation-feed-fixtures-2026-11-06.md),
not the subsequently generated BitBake fixture set. Its SHA-256 is
`392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6`.

The runner was invoked with `--case unsigned-rpm`; the retained command log is
`/workspace/int-linux-work/qemu-feed-unsigned-20261106.log`, SHA-256
`0a26edf2f12a1ac9404770acb11cb0ec08f9ad10ea5f26ef54786d7ec50349e9`.
Detailed evidence is in
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T222938.109048Z-135c19e55cb6/`:

| Artifact | SHA-256 |
| --- | --- |
| `result.json` | `f5ff5fc809fb2047558cc6e48c8fb49839eb437f9c2830da675cbe7a43f5643f` |
| `serial.log` | `e39d301e72579656ffb51e828d470933d6b7f535c4d14183c12bd3fa87b0f92e` |
| Input and snapshot root filesystem | `c215fe66e9067a144b787a8963095fac24cb08ad46f4b2e1cf230b75651b1698` |
| Input and snapshot kernel | `7a2df4e81ed894eee909f600911214b546402b2507bc25dd13c0944b91bbcd1d` |
| Input and snapshot manifest | `466236c761fe34a7078492965ce54d023c912059fc9e680a47aef102cbda02cb` |
| Input and snapshot fixture disk | `392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6` |

The runner reported no changed input or snapshot hashes after QEMU exited.

## Observed result

After pinning the key and installing version 1.0, DNF successfully created
the unsigned-package repository's metadata cache with signature checking
enabled and confirmed that its candidate was `int-feed-probe 2.0 r0`. A
separate strict `rpmkeys` check returned a nonzero status and printed
`signature: NOTFOUND` while package digests were `OK`. The attempted DNF
upgrade then returned nonzero with both of these diagnostics:

```text
Package int-feed-probe-2.0-r0.noarch.rpm is not signed
Error: GPG check FAILED
```

The guest checked the RPM database and installed version file still contained
version 1.0. The serial transcript contains these eight ordered markers:

```text
INT_FEED_CHECK:pin:PASS
INT_FEED_CHECK:install-v1:PASS
INT_FEED_CHECK:unsigned-metadata:PASS
INT_FEED_CHECK:unsigned-rpmkeys:PASS
INT_FEED_CHECK:unsigned-dnf-rejected:PASS
INT_FEED_CHECK:unchanged-v1:PASS
INT_FEED_CASE:unsigned-rpm:PASS
INT_FEED_SHUTDOWN
```

The runner observed the kernel's `reboot: Power down`, QEMU exit code 0,
no timeout or output limit, and no failure reasons. Total elapsed time was
47.902 seconds and `result.json` recorded `passed`. A previous independent
positive guest test installed version 1.0 and upgraded it to a correctly
signed version 2.0; see
[validation-feed-vm-2026-11-06.md](validation-feed-vm-2026-11-06.md).

The positive scenario was also repeated successfully on the same rebuilt
image used for this unsigned-package test, in a separate QEMU snapshot. Its
six checks passed, QEMU exited 0 and no failure reasons were reported. The
result is retained at
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T223054.631612Z-77776edacc34/result.json`,
SHA-256 `8a9f271eabb05589b558c3be70f162b88d8ee64c79dea639cba879c02daa833f`.
The command log is
`/workspace/int-linux-work/qemu-feed-success-after-unsigned-20261106.log`.
