# Disposable signed-feed fixtures

`int-feed-lab-native` has an explicit `create_feed_fixtures` task for preparing
artifacts for the proposed isolated VM experiment. The generator has been
executed successfully with copied OE native tools in a separate container;
the `create_feed_fixtures` BitBake task has not yet succeeded. See the
[isolated validation](validation-feed-fixtures-2026-11-06.md) for paths,
hashes and limits. The output is not evidence that DNF or the guest accepts
or rejects it, a release signing system, or a production repository.

First build and copy both unsigned `int-feed-probe` RPMs as described in
[feed-probe.md](feed-probe.md). Wait for all other INT build operations to
finish. Open `./scripts/int --profile feed shell` and run the following inside
that shell, replacing the example directory with the actual directory printed
by the probe-copy procedure:

```sh
probe_dir=/work/int-feed-probe.EXAMPLE
fixture_name="experiment-$(date -u +%Y%m%dT%H%M%SZ)"
config=/work/int-feed-fixture-input.conf
cat > "$config" <<EOF
INT_FEED_V1 = "$probe_dir/int-feed-probe-1.0-r0.noarch.rpm"
INT_FEED_V2 = "$probe_dir/int-feed-probe-2.0-r0.noarch.rpm"
INT_FEED_OUTPUT = "$fixture_name"
EOF
if bitbake -R "$config" -c create_feed_fixtures int-feed-lab-native; then
  printf 'Fixture directory: /work/feed-fixtures/%s\n' "$fixture_name"
else
  printf 'Fixture generation failed; inspect the task log.\n' >&2
fi
```

The two input paths must be exact filenames, regular files in the same direct
child `/work/int-feed-probe.*`, each between 1 byte and 10 MiB. Do not point
at deploy files. The output name accepts only letters, digits, underscore,
hyphen and dot, starts with an alphanumeric character, and has at most 64
characters. The task creates a new directory `/work/feed-fixtures/NAME`; it
will not reuse an existing path. Generated files are limited to 100 MiB in
total. Input copies are read-only and never signed in place.
The workspace must not be writable by an untrusted concurrent process: these
path checks reject ordinary mistakes and static symlinks, but do not defend
against another process replacing directories between checks and file access.

Successful creation produces a `manifest.json` last, after the temporary key
directory has been removed. It records the trusted **test** key's full primary
fingerprint, input and output hashes, and native tool versions. A directory
without a complete manifest is an incomplete attempt, not a successful run.
The native toolchain, test key, output and manifest are all experimental.

| Directory | Candidate presented to the future VM |
| --- | --- |
| `valid-v1`, `valid-v2` | One correctly signed probe and signed metadata for each version |
| `wrong-key-metadata` | Version 2 with metadata signed by a different untrusted key |
| `altered-repomd` | Version 2 with modified metadata after signing |
| `missing-metadata-signature` | Version 2 without the detached signature |
| `altered-primary` | Signed `repomd.xml` whose primary metadata was later modified |
| `stale-rpm-checksum` | Signed metadata whose referenced RPM was later modified |
| `unsigned-rpm` | Unsigned version 2 with freshly indexed and correctly signed metadata |
| `wrong-key-rpm` | Wrong-key version 2 with freshly indexed and correctly signed metadata |
| `corrupt-rpm-indexed` | Corrupt signed version 2 with freshly indexed and correctly signed metadata |

The task checks input RPM metadata for scriptlets, package and file triggers,
and permits only `/usr`, `/usr/share`, the probe directory and a regular
version file in the listed paths. It does not inspect the version file's
payload. It checks generated primary indexes contain exactly the intended RPM
and its SHA-256, verifies
that the two stale-checksum variants fail at their intended checks, and checks
selected signatures with the native tools. It does not
perform a complete metadata audit, a DNF transaction or a target runtime test.
In particular, refreshing the metadata around negative RPMs is intended to
allow a guest to reach the package check; only the future guest test can prove
that DNF actually reaches and rejects it for the intended reason.

Keys use an unmistakable laboratory identity, are unprotected and expire one
day after creation. The helper stops its GnuPG agents and removes temporary
homes on ordinary success, errors and SIGTERM before emitting a final manifest.
SIGKILL, host failure, or storage failure can leave temporary material behind;
this is not secure erasure and must never be used with real keys. The public
key is retained as `trusted-public-key.asc`; no private key is copied to the
fixture directory. An abandoned `/tmp/int-feed-fixtures-*` directory must be
inspected and removed by its owner after an interrupted run.

A future runner must pin the expected full fingerprint independently of the
virtual repository disk, use a new guest/cache for each rejection case, and
record DNF's actual diagnostics and the unchanged installed version. The
manifest and its key file alone are not an independent trust anchor. See
[feed-vm-plan.md](feed-vm-plan.md) for the remaining guest acceptance criteria.
