# Read-only feed audit with OE native tools — 2026-11-08

The opt-in `audit_feed_fixtures` task of `int-feed-lab-native` passed all ten
fixture cases with OE-built RPM/Sequoia 4.20.1, GnuPG 2.5.17, libgcrypt
1.12.4 and Python 3.14.7. No parser changes to `scripts/feed-check.py` were
needed. The two valid feeds passed the full chain including trusted-key
signature acceptance and empty-database NOKEY control. Negative cases count
only when both the expected verification stage and specific error are present;
a missing tool or earlier unrelated failure cannot count as rejection.

| Fixture | Result / diagnostic |
| --- | --- |
| valid-v1, valid-v2 | complete audit passed |
| wrong-key-metadata | ERRSIG / NO_PUBKEY / FAILURE |
| altered-repomd | BADSIG / FAILURE |
| missing-metadata-signature | missing detached signature |
| altered-primary | metadata checksum mismatch |
| stale-rpm-checksum | indexed RPM checksum mismatch |
| unsigned-rpm | RPM signature NOTFOUND |
| wrong-key-rpm | RPM signature NOKEY |
| corrupt-rpm-indexed | payload digest BAD |

The fixture file hashes were identical before/after. Each case's JSON and
stderr are retained under `/workspace/int-linux-work/feed-audits/native-20261108/`.
Summary SHA-256: `9977c79700a7553ac18e029c8c712b1cf4c4a75f8564cf4641df29c1d593bdde`.
Build log: `/workspace/int-linux-work/feed-audit-task-20261108.log`;
881 tasks, 876 already satisfied, all succeeded.

## Repeat

Generate fresh public fixtures first; never reuse expired disposable keys.
In a private post-read configuration file, set:

```bitbake
INT_FEED_AUDIT_FIXTURES = "YOUR-FIXTURE-NAME"
INT_FEED_AUDIT_FINGERPRINT = "INDEPENDENT_40_UPPERCASE_HEX_FINGERPRINT"
INT_FEED_AUDIT_OUTPUT = "NEW-OUTPUT-NAME"
```

Run in the configured feed builder, under the INT operation lock:

```sh
bitbake -R /work/YOUR-AUDIT.conf -c audit_feed_fixtures int-feed-lab-native
```

Input is `/work/feed-fixtures/YOUR-FIXTURE-NAME`; output is a new directory
under `/work/feed-audits`. Existing output is never overwritten. The auditor
receives only public keys and local fixture paths. It neither signs nor
installs, and temporary trust databases/keyrings are deleted by the auditor.
No default build/profile executes this opt-in task. Tests in
`tests/test_feed_audit_matrix.py` ensure unrelated failures cannot qualify.

This is native file-audit evidence, separate from the target QEMU records.
It does not qualify HTTPS, freshness, release key custody, a public server,
key rotation or interrupted-update recovery.
