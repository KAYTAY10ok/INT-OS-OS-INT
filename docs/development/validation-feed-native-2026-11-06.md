# Native RPM signature laboratory validation — 2026-11-06 UTC

The isolated `feed` profile has passed its first **native-tool** signature
laboratory. RPM 4.20.1 with Sequoia verified a disposable signed RPM using its
test public key; GnuPG 2.5.17 verified a detached signature of a generated
`repomd.xml`. These results do not qualify DNF, the target image, a published
feed, or the complete chain of repository metadata checksums.

The successful run was `./scripts/int --profile feed build
int-feed-lab-native`. Its retained console log is
`/workspace/int-linux-work/feed-lab-20261106-retry2.log`, SHA-256
`444fc77c1706936ccfc8f1a0147d637f263ea46b2f6916922ec43f2246ad4ce5`.
BitBake completed all 1,328 tasks, 1,319 already satisfied, and reported no
failed tasks. The preceding native RPM build, including Sequoia, also passed:
`/workspace/int-linux-work/build-rpm-sequoia.log`, SHA-256
`a74c1538d560c9892db3a721e5f7e1216a8533e09294d645db88fdb4fdd4d2a0`.

## Observed cases

The test used temporary RPM databases and two freshly created, unprotected
one-day test keys. It signed a copy of a tiny RPM, generated repository
metadata with createrepo_c 1.2.3 and verified the following outcomes. Each
negative result also checks a relevant diagnostic; a nonzero status alone is
not sufficient.

| Case | Observed exit |
| --- | ---: |
| Trusted signed RPM with `_pkgverify_level all` | 0 |
| Signed RPM with missing trusted key | 1 |
| Signed RPM with wrong trusted key | 1 |
| Unsigned RPM with the default digest policy | 0 |
| Unsigned RPM with `_pkgverify_level all` | 1 |
| Altered signed RPM | 1 |
| Trusted detached `repomd.xml` signature | 0 |
| Metadata signed by an unknown key | 2 |
| Modified `repomd.xml` | 1 |
| Missing detached metadata signature | 2 |

The successful unsigned default-policy control demonstrates why a valid digest
alone cannot establish a signature policy. The strict-policy rejection is a
native RPM test; it does not establish a DNF or target-image setting.

The disposable signing primary fingerprint was
`C768624B93A18C17C5741688C5F8A91D6AB763A7`. Its public-key SHA-256 was
`020f71e96e15d6e06ee3bb5d32656d97f4ffcd04fc6ee193025c555f99831436`.
The run reported successful cleanup of its temporary homes before emitting
the final JSON; its test key and fixtures are not release trust material and
the generated artifacts were not retained for independent re-verification.
The JSON in the retained log records the hashes of those ephemeral artifacts.

## Earlier failures and correction

The first attempt, `/workspace/int-linux-work/feed-lab-20261106-native.log`,
failed before signature checks. The RPM build's host `file` 5.45 tried to
read the native `magic` database from 5.47, producing non-UTF-8 diagnostics
and a Python decoding error. The laboratory now explicitly selects
`file-native` via its OE sysroot. Commit `bce7c13` contains that correction.

`/workspace/int-linux-work/feed-lab-20261106-retry1.log` then stopped during
recipe parsing because a concurrently developed test recipe referenced a file
not yet present. It did not execute the laboratory. The successful retry above
followed after that input was available. Both failed logs remain evidence and
are not counted as passing runs.

## Remaining work

Build the two actual `int-feed-probe` versions and exercise the fixture
generator with the native tools. Build the experimental target image, then
test the explicit trust policy and install/update/rejection paths in a
disposable guest. The metadata checksum chain, DNF trust behavior, target RPM
backend, network transport, freshness, key rotation, interrupted-update
recovery, production key custody and release publication remain unqualified.
See [signed-feed-plan.md](signed-feed-plan.md) and
[feed-vm-plan.md](feed-vm-plan.md).
