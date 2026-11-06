# Positive local DNF feed test in QEMU — 2026-11-06 UTC

The experimental `int-image-feed-smoke` image booted in QEMU and completed
the positive local-feed scenario. With a separately supplied test-key
fingerprint and signed `file://` repositories, DNF installed
`int-feed-probe` 1.0, upgraded it to 2.0 and repeated the upgrade with no
changes. The guest checked both the RPM database version and the installed
version file after each transaction. This is one positive virtual test: the
rejection cases, real network delivery and production update service are not
validated.

## Build and test inputs

`./scripts/int --profile feed build int-image-feed-smoke` completed 3,963
tasks, of which 2,502 were already up to date, with no failures. The retained
log is `/workspace/int-linux-work/build-image-feed.log`, SHA-256
`2848a58f753c9f1b674229b76af3bd73ca7705b94749e60d6db14dda2bb5e9ee`.
The image manifest contains `dnf` 4.24.0, `rpm` 4.20.1, `gnupg` and
`gnupg-gpg` 2.5.17, plus the test-only service. The boot kernel release was
`6.18.54-int-core1`.

The runner used a root filesystem snapshot, a separate read-only virtio EXT4
fixture disk and no network device. QEMU 8.2.2 ran with TCG and `qemu64`.
The independently supplied disposable test-key primary fingerprint was
`D8F858DAF212985476049E82F0FD22E0B698895A`; it expires at
2026-11-07 13:19:05 UTC. It is not release trust material. Fixture creation,
the public key and disk are described in
[validation-feed-fixtures-2026-11-06.md](validation-feed-fixtures-2026-11-06.md).

The command was:

```sh
./scripts/int --profile feed feed-check /work/feed-disks/isolated-test/feed.ext4 \
  --fingerprint D8F858DAF212985476049E82F0FD22E0B698895A \
  --disk-sha256 392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6
```

The command output is retained at
`/workspace/int-linux-work/qemu-feed-first-20261106.log`. The detailed record
and serial transcript are in
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T222329.640719Z-14b5cb86ba1c/`:

| Evidence | SHA-256 |
| --- | --- |
| `result.json` | `5eaccbc33927eefce14f611de9a892de418372349fa6c7d17b4cb76f81264a20` |
| `serial.log` | `ae57d21c059f8a410fd675aa9590565146428a9423b52ad9da58c0182730a298` |
| Input and snapshot fixture disk | `392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6` |
| Input and snapshot root filesystem | `3fc5424646f7ad7d1faee9dee22254e00eedd57fff7f699c4528046b5ba9181f` |
| Input and snapshot kernel | `7a2df4e81ed894eee909f600911214b546402b2507bc25dd13c0944b91bbcd1d` |
| Input and snapshot image manifest | `466236c761fe34a7078492965ce54d023c912059fc9e680a47aef102cbda02cb` |

The runner recorded no changed input or snapshot hashes after QEMU exited.

## Observed result

The guest checked the full public-key fingerprint before import. Its DNF
configuration set `gpgcheck=1`, `repo_gpgcheck=1`, `localpkg_gpgcheck=1`,
and `skip_if_unavailable=0`, with other repositories disabled. The serial log
records metadata key import and successful DNF transactions. It reports
`Nothing to do` on the repeated upgrade, followed by these six ordered
markers:

```text
INT_FEED_CHECK:pin:PASS
INT_FEED_CHECK:install-v1:PASS
INT_FEED_CHECK:update-v2:PASS
INT_FEED_CHECK:repeat-v2:PASS
INT_FEED_CASE:success:PASS
INT_FEED_SHUTDOWN
```

The runner also observed the kernel's `reboot: Power down`, QEMU exit code 0,
no timeout or output limit, and no failure reasons. Total elapsed time was
49.893 seconds. The final `result.json` status is `passed`.

The successful transactions do not prove that DNF rejects unsigned, tampered,
missing-signature or wrong-key inputs. Those negative cases need fresh guest
snapshots and case-specific diagnostics. This result also does not establish
HTTPS delivery, production key custody, freshness or anti-replay policy,
interrupted-update recovery, physical hardware behavior, or release readiness.
