# Isolated signed-feed fixtures validation — 2026-11-06 UTC

The fixture generator completed successfully using the two actual
`int-feed-probe` RPMs and native RPM/GnuPG/createrepo tools copied from the
OE build. It created a public manifest covering 60 files in ten disposable
feed variants. This was a direct invocation in an isolated container, **not**
an execution of the `create_feed_fixtures` BitBake task. It did not exercise
DNF, the target image or a complete repository audit.

## Setup and evidence

While the target image build was active, the native recipe sysroot and its
required `sysroots-uninative` dynamic loader were copied into a private
scratch workspace at their expected paths. Copies of the two unsigned probe
RPMs and the generator scripts were used. The container had no network, a
read-only root filesystem, and a private writable `/work`. Its `/tmp` was a
memory-backed filesystem used for temporary GnuPG homes. The active build
workspace was not mounted in the container. The generator completed with exit
code 0 and emitted its final manifest after stopping its test agents and
removing its temporary key homes. Container termination discarded the
memory-backed `/tmp`.

The retained console log is
`/workspace/int-linux-work/validation-isolated-feed-fixtures.log`, SHA-256
`7e47b7649467c08271f976e07b24e5df6834811e047deb2e791a7d90cfd8e9d1`.
It records the input and script hashes, generated artifact hashes, test
fingerprint and tool versions. Native versions were RPM 4.20.1, GnuPG 2.5.17
and createrepo_c 1.2.3. The public fixture tree is
`/workspace/int-linux-work/feed-fixtures/isolated-20261106/`; its
`manifest.json` SHA-256 is
`eb103c3c81e3fc98115887a9750ca568602c3b0baf561014b37b26f7bced94c1`.

The unprotected, disposable signing key's primary fingerprint was
`D8F858DAF212985476049E82F0FD22E0B698895A`. The test key was created at
2026-11-06 13:19:05 UTC and expires at 2026-11-07 13:19:05 UTC. It is not
production trust material. A guest test after expiry must create fresh
fixtures and independently pin the new public fingerprint.

## Fixture disk

`scripts/feed-disk.py` checked the fixture tree against its manifest and
constructed a 33,759,232-byte EXT4 image with mke2fs 1.47.0. The retained
image is `/workspace/int-linux-work/feed-disks/isolated-test/feed.ext4`,
SHA-256 `392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6`.
Its adjacent `report.json` records the source manifest and image hashes.
Manifest and file-hash checks establish only consistency with the supplied
manifest; they do not authenticate the manifest or the signing key. A guest
runner must receive the expected fingerprint independently of this disk,
attach it read-only, and verify the image hash before and after use.

The successful isolated generator run exercises native signatures and its
own index checks, not the BitBake task wrapper, guest behavior, DNF signature
enforcement, target RPM backend, package update, or the entire metadata
checksum chain. Those still require separate tests. The initial BitBake task
attempt failed before generating fixtures due to an implicit RPM database;
the generator now uses an explicit isolated database. A later BitBake task
run remains necessary to validate that execution route. See
[feed-fixtures.md](feed-fixtures.md), [feed-disk.md](feed-disk.md) and
[feed-vm-plan.md](feed-vm-plan.md).
