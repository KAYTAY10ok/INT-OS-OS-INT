# Shared console core validation — 2026-11-05 UTC

The console/account/firewall subset of Phase 2 now has a successful image build
and complete interactive VM test. This is a development milestone, not a release
or completion of the master specification. The earlier foundation evidence in
[validation-2026-11-05.md](validation-2026-11-05.md) remains independently preserved.

## Tested configuration and commands

The OE-Core and BitBake source pins remain unchanged. The source lock additionally
pins meta-openembedded to `c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e`, using its
meta-oe, meta-python and meta-networking layers for upstream nftables. There is
no parent distribution or foreign target package repository.

The kernel source remains 6.18.54 at the locked machine/metadata revisions. Its
new ABI is `6.18.54-int-core1`, recipe revision `r1`. The merged configuration has
NF_TABLES and NF_TABLES_INET built in, NF_CONNTRACK and NFT_CT as modules, and
VETH as an optional test module. The official netfilter fragment overrides the
earlier INT request for built-in conntrack; runtime packages are explicitly
installed rather than assuming the source fragment won.

```sh
./scripts/int bootstrap
./scripts/int configure
./scripts/int build virtual/kernel
./scripts/int check
./scripts/int build int-image-core-smoke
./scripts/int build int-image-core
./scripts/int core-check
python3 -m unittest discover -s tests -v
```

Actual outcomes:

- The effective configuration check passes, including generic m64 CPU flags,
  source revisions, kernel ABI and recipe revision. BitBake parsed 2,942 recipes
  with zero errors. Compiler hardening flags remain enabled.
- Kernel build: all 1,196 tasks succeeded, 1,161 reused.
- Non-test core image: all 3,250 tasks succeeded, 3,226 reused.
- Final core smoke rebuild after environment recovery: all 3,269 tasks succeeded,
  3,265 reused. SPDX image SBOM generation completed for both variants.
- Host tooling suite: **57 tests passed**. These include fake account backends,
  real local PTYs, malformed/mismatched kernel inputs, credential redaction,
  process cleanup and cross-process operation locks. They do not replace QEMU.

Only one helper operation may use a work directory at a time. A nonblocking
advisory lock covers normal CLI operations, including image snapshots. After an
unexpected interruption, still inspect live containers and generated outputs
before resuming; a file lock is not an orphan-process recovery service.

## Complete guest result

Successful run:
`INT_WORKDIR/evidence/qemu-smoke-20261105T212147.613206Z-638aa279a483/`.
Its `result.json` reports all seven groups passed, no timeout/interruption,
no credential echo, no protocol error, login UID 1000, wrong-password rejection
by sudo, QEMU exit 0, and kernel powerdown. `known-good.json`, the redacted serial
log and exact input copies are retained. The 54.223-second total includes setup,
interactive authentication and network tests; it is not a boot benchmark.

The real guest checks:

- First-owner enrollment through upstream passwd/PAM, locked root, protected
  owner records, usable owner shell/group and unchanged account databases on
  repeat enrollment. No test password or hash is embedded in the image.
- Active nftables policy, repeated atomic reloads, invalid-transaction rejection,
  and preservation of an unrelated table.
- A real TCP token over loopback, a new inbound connection timing out, success
  with a narrow temporary accept rule, then another timeout after its removal.
- Missing and invalid policy files causing real nftables startup failure and
  preventing networkd activation. Previously installed rules remain present.
  Restoring the original file recovers both services and the policy.
- A DHCP address, active link, connected route and no IPv4 default route under
  QEMU `restrict=on`, after service recovery.
- Actual console login as the unprivileged owner; a wrong sudo password rejected
  before a fresh prompt and acceptance of the correct password; root helper and
  clean guest poweroff.

QEMU uses TCG/qemu64, two virtual CPUs and 512 MiB RAM, with no host port forward.
This verifies the conservative CPU target, not hardware minimums. Passwords stay
in runner memory. Guest modifications use a temporary disk overlay; retained
input images remain unprovisioned. Test helpers exist only in the smoke variant.

## Artifact identity and retained evidence

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Kernel | 13,857,792 | `be7d6786e2f567044cf4b0913d7dfce2b416109cb2d47ad81aaf90f79c42d1ee` |
| Core ext4 | 163,566,592 | `2ab4d6ced005400b82c603f4f469df98e8c1248c72e657c03758cd1136001161` |
| Core smoke ext4 | 174,971,904 | `d650ba1dc8c32d735504ca723de6eb2ad32aaa40bbeed199e4262b7c9e64635b` |

The production core has 120 packages and a 42,978,022-byte tar.zst archive. An
offline archive audit confirms locked root, no preconfigured test owner, no smoke
package/helpers, and presence of enrollment/firewall/sudo configuration. The full
interactive boot above used the smoke variant; the production archive audit is
not a separate production-image login test. Storage sizes are not RAM metrics.

`INT_WORKDIR/evidence/shared-core-20261105T212416Z/` retains production artifacts,
both image SBOMs, build/test logs and `build-manifest.json` with source hashes.
`INT_WORKDIR/evidence/core-kernel-config-20261105T205356Z-6c21053c/` retains the
merged `.config`, audit reports and kernel/source inputs. Its configuration hash
is `36625d17843a4fc0871a26e52138f6bb3236fff544c1e4e3154230e4419e518d`.
Module-presence audits pass against both final image manifests.

The VM preflight compares the bzImage header release with the exact kernel and
module package names in the copied manifest. It rejects the old foundation rootfs
paired with the new ABI. Identical release names alone do not bind kernel/module
content; retain hashes and rebuild the coherent image after source changes.

## Failures investigated and corrected

- RPM initially rejected conflicting directory modes for `/etc/sudoers.d`. INT
  now preserves upstream sudo's 0750 directory and 0440 policy file. No package
  conflict/signature check was bypassed. Evidence: `core-build-failure-20261105T210857Z`.
- First VM: enrollment, reload, invalid-transaction and loopback checks worked,
  but the veth test server could not start. Its interface name matched upstream
  networkd's generic Ethernet DHCP profile. Test links now use the excluded
  `veth*` prefix; all packet controls subsequently pass. Failed run retained:
  `qemu-smoke-20261105T211253.990690Z-41ba43674dd4`.
- A cloud restart interrupted the third smoke build during final SBOM generation.
  Recovery found no active compiler; the resumed build reused 3,265 tasks and
  completed the four remaining tasks successfully.
- Second VM completed every guest network check and reached login, but the PTY
  supplied CR-CR-LF while the runner expected at most one CR. That diagnostic
  run was interrupted to collect its redacted log; it is not a pass. Exact-line
  parsing now accepts repeated CR before LF and has a real PTY regression test.
  Run: `qemu-smoke-20261105T211656.090064Z-76e3a344f09b`.

## Remaining scope

Signed feeds, DNF client qualification, update/recovery transactions, desktop,
installer/live media, encryption, verified boot, MAC profiles, full privacy/lab
isolation, physical hardware and performance qualification remain open. Inspect
[signed-feed-plan.md](signed-feed-plan.md): the existing RPM native backend lacks
OpenPGP support; digest-only verification cannot qualify signatures. The selected
desktop layer/components are researched in [desktop-integration-plan.md](desktop-integration-plan.md),
not integrated. Review kernel patch-level/security gaps before release.
No code push, release deployment or environment publication was performed.
