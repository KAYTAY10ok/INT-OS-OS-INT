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

## BitBake task retry

The initial `create_feed_fixtures` BitBake task failed before generating
fixtures because an RPM command tried to use an implicit database. After the
generator was corrected to use an isolated RPM database, the task completed
successfully: 881 tasks were attempted, 877 already up to date. The retained
log is `/workspace/int-linux-work/create-feed-fixtures-retry-20261106.log`,
SHA-256 `b1e74b736785569796d6fa4531477ba196a99a9c653a5d788b5702443d6b5b28`.

This second run produced a distinct set of 60 public fixture files under
`/workspace/int-linux-work/feed-fixtures/bitbake-20261106T222559Z/`; its
`manifest.json` SHA-256 is
`2cc48c3f120a10df20d9759b4725b1ff05a6d68c71572f52a60b02871bb56b41`.
Its disposable primary fingerprint is
`B196F513560A083034E3C61E2A82093247C6C3A2`; the test key expires one day
after creation. The manifest records RPM 4.20.1, GnuPG 2.5.17 and
createrepo_c 1.2.3. These are laboratory fixtures, not production trust
material.

The earlier **isolated** fixtures and disk described above—not this second
BitBake-generated set—were later used for the positive DNF guest test; see
[validation-feed-vm-2026-11-06.md](validation-feed-vm-2026-11-06.md). Neither
generator run alone establishes a complete metadata audit or negative DNF
signature enforcement. The task run does not establish the behavior of its
second fixture set in the guest. See [feed-fixtures.md](feed-fixtures.md),
[feed-disk.md](feed-disk.md) and [feed-vm-plan.md](feed-vm-plan.md).
