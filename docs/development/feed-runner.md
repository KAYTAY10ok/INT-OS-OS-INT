# Experimental local-feed QEMU runner

`scripts/qemu-feed-check.py` is the host runner for the experimental positive
DNF scenario. One QEMU run using a built feed image and real signed fixtures
passed: see [the validation record](validation-feed-vm-2026-11-06.md). It
does not establish that DNF rejects bad signatures.

The runner accepts only the `success` case. The guest must check the supplied
full test-key fingerprint, install probe version 1.0, update to 2.0, repeat the
update, check the RPM database and version file after each step, and emit the
six exact ordered markers in the runner. It also requires a kernel poweroff
message, QEMU exit status zero and unchanged input and snapshot hashes. The
runner rejects absent, duplicate, out-of-order or unknown feed markers,
failure messages, panics, timeouts, excessive serial output and input changes.

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
and test key expire and are never production credentials. Negative DNF cases,
metadata-chain auditing, network feeds, anti-replay, production key custody and
interruption recovery are outside this runner's present scope.
