# Experimental local-feed QEMU runner

`scripts/qemu-feed-check.py` is the host runner for experimental local DNF
scenarios. A positive QEMU run using real signed fixtures passed; see
[the validation record](validation-feed-vm-2026-11-06.md). A separate guest
run rejected an unsigned package while retaining version 1.0; see
[the unsigned-package record](validation-feed-unsigned-vm-2026-11-06.md).
Another run rejected a package signed by an untrusted key, also retaining
version 1.0; see [the wrong-key record](validation-feed-wrong-key-vm-2026-11-06.md).
A separate run rejected a repository whose detached metadata signature was
missing; see [the metadata record](validation-feed-missing-signature-vm-2026-11-06.md).
A further run rejected signed metadata modified after signing; see
[the altered-metadata record](validation-feed-altered-repomd-vm-2026-11-06.md).

The runner accepts `success`, `unsigned-rpm`, `wrong-key-rpm`,
`missing-metadata-signature` and `altered-repomd`. All require the supplied
full test-key fingerprint, installation of version 1.0, exact ordered markers,
a kernel poweroff message, QEMU exit status zero, and unchanged input and
snapshot hashes. The success case updates to 2.0 and repeats the update. The
package rejection cases verify signed metadata, require the corresponding
`rpmkeys` and DNF rejection, then check the installed version remains 1.0.
The wrong-key case also checks that a trusted signed RPM passes `rpmkeys`.
The missing-metadata case verifies a signed control and requires DNF to reject
the repository without its detached signature, with version 1.0 unchanged.
The altered-metadata case verifies a signed control and `BADSIG` on the
modified metadata, then requires DNF rejection with version 1.0 unchanged.
The runner rejects
absent, duplicate, out-of-order or unknown feed markers, failure messages,
panics, timeouts, excessive serial output and input changes.

An isolated run has prepared signed fixtures and an EXT4 disk; its
[validation record](validation-feed-fixtures-2026-11-06.md) gives the
independently recorded fingerprint, disk hash and key expiry. Once the image
is built and no other INT operation is running, use
`./scripts/int --profile feed shell`. Inside the shell, replace the uppercase
placeholders with the independently recorded
fingerprint and disk hash, without taking the fingerprint solely from the disk:

```sh
python3 /src/scripts/qemu-feed-check.py \
  /work/build-feed/tmp/deploy/images/qemux86-64 \
  /work/feed-disks/NAME/feed.ext4 /work/evidence \
  --fingerprint FORTY_UPPERCASE_HEX_CHARACTERS \
  --disk-sha256 SIXTY_FOUR_LOWERCASE_HEX_CHARACTERS
```

The default is `--case success`; select `--case unsigned-rpm`,
`--case wrong-key-rpm` or `--case missing-metadata-signature` to run that
rejection in a fresh QEMU snapshot. Use `--case altered-repomd` for the
modified-metadata case.

The manifest must include `int-feed-smoke`, `dnf`, `rpm`, `gnupg` and
`gnupg-gpg`, and its kernel package must match the copied kernel ABI. The runner snapshots the
kernel, rootfs, manifest and pinned fixture disk; guest root writes go to a
temporary QEMU overlay. The fixture disk is a separate read-only virtio drive,
and QEMU has no network device. The evidence directory retains a `result.json`
and bounded serial log for both successes and failures. This is a virtual test,
not a release or a physical hardware qualification.

The supplied disk hash protects against using a different disk from the one the
operator recorded; it does not authenticate the disk creator. The full signing
fingerprint must come from an independent trusted record. The public fixtures
and test key expire and are never production credentials. Other negative DNF
cases, complete metadata-chain auditing, network feeds, anti-replay, production
key custody and interruption recovery are outside this runner's present scope.

The `corrupt-rpm-indexed` case also tests rejection of payload corruption with
freshly signed metadata; see [VM evidence](validation-feed-corrupt-vm-2026-11-08.md).
