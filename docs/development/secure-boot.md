# UEFI Secure Boot with owner-enrolled INT keys (MOK)

Status (2026-11-07): **design plus first tools only. INT images do not boot
with Secure Boot enabled yet.** The live ISO and installed systems still
require Secure Boot to be disabled. Nothing in this document has been
boot-tested on OVMF or real hardware.

The owner chose this model: INT binaries are signed with an **INT key**; the
user enrolls the matching **public certificate** as a Machine Owner Key (MOK)
through shim's MokManager. The private signing key is managed by the owner
outside the repository and never enters Git, BitBake metadata, the build tree
or logs.

What exists now:

| Item | Path | State |
| --- | --- | --- |
| Owner-side signing tool | `scripts/sign-boot.py` | Implemented, unit-tested with fake `sbsign`; ISO repack checked locally with real `xorriso`/mtools and a fake `sbsign` |
| Tests | `tests/test_sign_boot.py` | 24 tests, no real key involved |
| `mokutil` recipe | `meta-int/recipes-bsp/secureboot/mokutil_0.7.3.bb` | Pinned, **not built, not in any image** |
| `shim` recipe (unsigned build) | `meta-int/recipes-bsp/secureboot/shim_16.1.bb` | Pinned, **not built, not in any image** |
| Kernel fragment | `meta-int/recipes-kernel/linux/files/int-secureboot.cfg` | **Not referenced** by any recipe |

## 1. What the pinned layers provide

Checked in `/home/user/int-linux-work/sources` (OE-Core series `wrynose`).

| Need | Pinned layers | Notes |
| --- | --- | --- |
| GRUB EFI | `grub-efi_2.14.bb` (OE-Core) | `GRUB_MKIMAGE_OPTS` hook exists. **No `.sbat` section** is added (no `--sbat`), and only `GRUB_BUILDIN` modules are built in. GRUB ≥ 2.06 enables its `shim_lock` verifier and lockdown automatically when Secure Boot is on and shim's protocol is present. |
| gnu-efi | `gnu-efi_4.0.4.bb` | Not needed by shim 16.1, which builds its bundled copy. |
| efivar / efibootmgr | `efivar_39.bb`, `efibootmgr_18.bb` | Present; the installer already uses efibootmgr. |
| keyutils | `meta-oe/.../keyutils_1.6.3.bb` | Needed by mokutil. |
| Kernel module signing | `kernel.bbclass`, `lib/oe/package.py` | Kernel builds sign modules when `CONFIG_MODULE_SIG_ALL` is set; OE avoids stripping signed modules. **Caution:** `do_shared_workdir` (which has an sstate setscene) copies `certs/signing_key.*`, including the private `signing_key.pem`, into `STAGING_KERNEL_BUILDDIR` (see section 5). |
| `kernel-signing-keys-native` | OE-Core | FIT/U-Boot only, generates keys in the build. Not applicable and not wanted. |
| `uki.bbclass` | OE-Core | Can build a Unified Kernel Image; its signing needs `sbsign-tool-native`, which lives in meta-secure-core (not pinned). |
| `signing.bbclass` | meta-oe | PKCS#11/SoftHSM signing inside BitBake. Rejected for now: with file keys the key is imported into the build, and HSM PINs would sit in `local.conf`. |
| **shim** | missing | Upstream https://github.com/rhboot/shim, release **16.1**, tag commit `afc49558b34548644c1cd0ad1b6526a9470182ed`, tarball `https://github.com/rhboot/shim/releases/download/16.1/shim-16.1.tar.bz2`, sha256 `46319cd228d8f2c06c744241c0f342412329a7c630436fce7f82cf6936b1d603`. Recipe added (unsigned build). |
| **mokutil** | missing | Upstream https://github.com/lcp/mokutil, tag **0.7.3** = commit `9ddb02fd2e3f5a2cc4dc3b4eacfe2f099916f548`, GPL-3.0-or-later. Recipe added. |
| **sbsigntools** (`sbsign`, `sbverify`) | missing | Upstream https://git.kernel.org/pub/scm/linux/kernel/git/jejb/sbsigntools.git, tag **v0.9.5** (tag object `8445b18f64e60137408a4867fbcbb9ba112c583a`, commit `9cfca9fe7aa7a8e29b92fe33ce8433e212c9a8ba`); snapshot `sbsigntools-0.9.5.tar.gz` sha256 `a2323e54be6d17f50ceb3253ca6ed063171a5bcb7079bfa594008cd2aeb7fdea`. Needs the `lib/ccan.git` submodule at `b1f28e17227f2320d07fe052a8a48942fe17caa5` (upstream `git://git.ozlabs.org/~ccan/ccan`, mirror https://github.com/rustyrussell/ccan). **No recipe added:** signing runs on the owner's host with the distribution package (Debian/Ubuntu `sbsigntool`, Fedora `sbsigntools`), and a cross recipe needs patches because `configure.ac` hard-codes host gnu-efi paths (`/usr/include/efi`, `/usr/lib*/crt0-efi-*.o`). |
| **efitools** | missing | Upstream https://git.kernel.org/pub/scm/linux/kernel/git/jejb/efitools.git, tag **v1.9.2** = commit `392836a46ce3c92b55dc88a1aebbcfdfc5dcddce`. Only needed for option 4 below (own PK/KEK). No recipe added. |
| pesign | missing | Alternative to sbsign (NSS database). Not needed. |

## 2. The realistic Secure Boot options

Factory PCs trust only what is in firmware `db`: in practice Microsoft's
Windows CA and, on most PCs, the **Microsoft third-party UEFI CA** (the 2011
CA, and the 2023 CA on updated firmware). A binary signed only with the INT
key is rejected by the firmware itself. shim exists to bridge this: a shim
signed by Microsoft's third-party CA is accepted by the firmware and then
trusts, in addition to `db`, its own embedded vendor certificate and the
user's **MOK list**.

1. **Microsoft-signed shim + INT certificate enrolled as MOK — this is the
   owner's "MOK" choice.** The user boots, MokManager enrolls
   `INT-SecureBoot.cer` once (physical presence), and from then on
   INT-signed GRUB and kernels boot with Secure Boot on. Where the
   Microsoft-signed shim comes from:
   - **1a. INT's own shim, reviewed and signed.** Submit a reproducible build
     of a tagged shim with an embedded INT vendor CA to
     https://github.com/rhboot/shim-review. Reviewers require, among other
     things: an HSM-protected signing key, SBAT entries for INT, a GRUB with
     all published CVE fixes and current SBAT generation, kernel lockdown and
     enforced module signing, and named security contacts. After acceptance
     the binary is submitted to Microsoft through a Partner Center (hardware
     dashboard) account that needs an EV code-signing certificate. This takes
     months and an organisation; it is the clean long-term answer.
   - **1b. Another distribution's Microsoft-signed shim.** E.g. Debian's
     `shim-signed` (`shimx64.efi.signed` and the matching
     `mmx64.efi.signed`) or Fedora's `shim-x64`. These shims honour MOK, so
     INT-signed GRUB and kernels boot after enrollment. It works today but:
     INT depends on that vendor's revocations (a revoked shim stops booting
     until replaced), shim and MokManager must come from the same package
     and be pinned by exact package version and sha256, INT's GRUB must carry
     a `.sbat` section with a non-revoked generation, and the redistribution
     should be stated in the release notes. It is the only route that
     satisfies "MOK" without a shim-review.
   - Some PCs (e.g. "Secured-core" models) ship with the third-party CA
     disabled; the user must enable it ("Allow Microsoft 3rd party UEFI CA")
     in firmware setup. Firmware whose `db` lacks the CA that signed the
     chosen shim (2011 vs 2023) needs a `db` update first.
2. **Self-built, unsigned shim (`shim_16.1.bb`) + INT certificate added to
   firmware `db` by the user.** Shim, MokManager and fallback are then signed
   with the INT key (`sign-boot.py --sign-shim`). This needs a firmware setup
   UI that can append a certificate to `db` (not universal) and is **not**
   the MOK model: MOK is optional on top. Without the `db` enrollment the
   firmware refuses this shim before MokManager can even start, so
   "self-signed shim + MOK" alone cannot work.
3. **No shim: INT-signed GRUB with the INT certificate in `db`.** Simpler, but
   GRUB then has no `shim_lock` protocol to verify the kernel; behaviour must
   be proven on OVMF first. Not recommended.
4. **Owner-controlled PK/KEK/db** (efitools/sbkeysync, firmware in Setup
   Mode). Full control, but removing Microsoft keys can brick PCs whose GPU
   or storage option ROMs are Microsoft-signed. Experts only.
5. **Secure Boot disabled** — the current state of INT.

Enrolling the *hash* of a GRUB binary in MokManager ("Enroll hash from disk")
also works but must be repeated for every GRUB update; not suitable.

**Recommendation:** implement option 1b now (pinned Microsoft-signed shim from
one distribution), keep the chain identical to what 1a will need, and start
1a when INT has an organisation, an HSM and security contacts.

## 3. Chain of trust

```
firmware db (Microsoft 3rd-party UEFI CA)
  └─ shimx64.efi            Microsoft-signed (1a/1b)  → EFI/BOOT/BOOTX64.EFI
       ├─ mmx64.efi         MokManager, same vendor as shim
       └─ grubx64.efi       signed with INT key, verified against MokList
            │  embedded config, all modules built in, .sbat section,
            │  shim_lock verifier + GRUB lockdown (automatic under SB)
            └─ bzImage      PE (EFI stub), signed with INT key,
                 │          verified by GRUB through shim_lock
                 ├─ lockdown=integrity forced (CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY)
                 └─ modules signed at build time with a one-off key whose
                    certificate is built into this bzImage;
                    CONFIG_MODULE_SIG_FORCE refuses anything else
```

Trust for modules is transitive: the owner signs the kernel image, and that
image is the only place the one-off module certificate is trusted.

**Not covered by this chain** (see section 9): the initrd, `grub.cfg` read
from disk, the kernel command line if GRUB's editor is reachable, and the
root filesystem (`rootfs.img` on the ISO, the installed ext4/LUKS root).

### GRUB requirements for the Secure Boot variant

- `--sbat` file for `grub-mkimage` (via `GRUB_MKIMAGE_OPTS` in a
  `grub-efi` bbappend), for example:
  ```
  sbat,1,SBAT Version,sbat,1,https://github.com/rhboot/shim/blob/main/SBAT.md
  grub,5,Free Software Foundation,grub,2.14,https://www.gnu.org/software/grub/
  grub.int,1,INT Linux,grub,2.14,<INT project URL>
  ```
  The `grub` generation must be at least the one revoked by the newest
  `SbatLevel` in the chosen shim (`SbatLevel_Variable.txt` in shim 16.1 ends
  at `grub,5`); re-check this whenever shim or GRUB changes. shim 16.1
  refuses any second stage without `.sbat` (`pe.c`, `verify_sbat_section`);
  `sign-boot.py` refuses to install a shim in front of such a GRUB.
- Never pass `--disable-shim-lock`.
- Every module GRUB needs must be in `GRUB_BUILDIN`: under Secure Boot
  `insmod` of a module file is refused. Audit the generated `grub.cfg` for
  `insmod`.
- Replace OE's embedded `cfg` (`search --file --set=root ... /EFI/BOOT/grub.cfg`)
  by a config that does not `search` other disks: with search, a USB stick
  carrying its own `/EFI/BOOT/grub.cfg` can supply the menu and kernel
  command line. Preferred: the menu itself embedded in the signed image
  (live: fixed entries; installed: fixed `root=PARTLABEL=...`, see section 7)
  and the GRUB editor/console locked (`set superusers=...` with a password, or
  no interactive entry).

## 4. Key hierarchy and generating the owner key

Phase 1 (simplest): one key pair.

- `int-sb-<year>.key` — RSA-2048 private key, passphrase-encrypted, **only**
  on the owner's offline/encrypted medium. RSA-2048 is the size every UEFI
  implementation must support, which keeps option 2 open.
- `int-sb-<year>.crt` — public certificate (PEM); safe to publish and
  later to commit.
- `INT-SecureBoot.cer` — the same certificate in DER, what users enroll.
  `sign-boot.py` writes it to every ESP it signs.

Phase 2 (recommended before wide distribution): an offline **INT Secure Boot
CA** (`CA:TRUE, pathlen:0`, enrolled as the MOK, kept cold) issuing a
short-lived **signing certificate** (`codeSigning`) used by `sign-boot.py`.
A leaf can then be rotated without users re-enrolling. Revoking a leaf still
needs `mokutil --mokx` on each machine (INT does not control the SBAT level of
a third-party shim), so protect the leaf key as well. `--chain` passes extra
intermediates to `sbsign --addcert` if the hierarchy is deeper.

Generate on the owner's machine, never in a checkout, never in the build
host's `INT_WORKDIR`, never in a shell whose output is logged:

```sh
umask 077
KEYDIR=/media/int-keys          # encrypted, offline medium
mkdir -p "$KEYDIR" && chmod 700 "$KEYDIR"
# No -noenc: OpenSSL asks for a passphrase and encrypts the key.
openssl req -new -x509 -newkey rsa:2048 -sha256 -days 3650 \
  -subj "/O=INT Linux/CN=INT Linux Secure Boot 2026" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature" \
  -addext "extendedKeyUsage=codeSigning" \
  -keyout "$KEYDIR/int-sb-2026.key" -out "$KEYDIR/int-sb-2026.crt"
openssl x509 -in "$KEYDIR/int-sb-2026.crt" -outform DER -out "$KEYDIR/INT-SecureBoot.cer"
openssl x509 -in "$KEYDIR/int-sb-2026.crt" -noout -fingerprint -sha256
openssl x509 -in "$KEYDIR/int-sb-2026.crt" -noout -fingerprint -sha1   # MokManager shows SHA-1
```

Make an encrypted backup of the key; losing it means every user must enroll a
new certificate. Publish the certificate fingerprints through a channel that
is independent of the ISO download (release notes, website).

Rules: the key is never copied into the repository, `INT_WORKDIR`,
`local.conf`, any BitBake variable, environment variable or log;
`.gitignore` ignores `*.key`, `*.p12`, `*.pfx` as a last safety net.

## 5. Signing without the key entering BitBake

Signing is a separate, post-build step on the owner's machine:

1. Build as usual: `./scripts/int --profile live build int-image-live`.
   BitBake produces **unsigned** GRUB and kernel; no BitBake variable names
   a key.
2. Copy the ISO to the owner's machine and run:
   ```sh
   scripts/sign-boot.py \
     --key /media/int-keys/int-sb-2026.key --cert /media/int-keys/int-sb-2026.crt \
     --shim shimx64.efi.signed --mokmanager mmx64.efi.signed \
     int-image-live-qemux86-64.iso int-image-live-signed.iso
   ```
   Without `--shim/--mokmanager` it signs GRUB and kernel in place
   (options 2/3, or for testing). `--sign-shim` additionally signs shim and
   MokManager (option 2 only; never re-sign a Microsoft-signed shim).
3. Publish the signed ISO, its SHA-256 and the certificate fingerprint.

What `sign-boot.py` guarantees:

- The key is passed by path to the host's `sbsign` only; the script never
  opens it, copies it or prints it. `sbsign` asks for the passphrase on the
  terminal.
- It refuses a key that is a symlink, not a regular file, not owned by the
  caller, group/world accessible (`chmod 600`), inside this repository, inside
  any Git checkout, or inside the input/output.
- It refuses a certificate file that contains a private key.
- INPUT (ESP directory copy or ISO) is never modified; OUTPUT must not exist
  and appears only after every signature was checked with `sbverify --cert`.
  Work happens in a private `0700` temporary directory next to OUTPUT, removed
  afterwards.
- It refuses a kernel that is not a PE image (`CONFIG_EFI_STUB` missing) and,
  with a shim, a GRUB without `.sbat`.
- ISO mode extracts the ISO with `xorriso`, signs the ISO-level ESP files
  (`/EFI/BOOT/bootx64.efi`, `/bzImage`) and the El Torito image `/efi.img`
  (unpacked and rebuilt with mtools), then writes a new ISO with
  `-boot_image any replay`. An appended EFI partition, which replay would
  otherwise copy **unsigned** from the old ISO, is replaced by the rebuilt
  `efi.img` (checked locally). ISO mode extracts the whole ISO, so it needs
  free space for one extra copy.

Host packages: `sbsigntool` (`sbsign`, `sbverify`), `xorriso`, `mtools`.

### Kernel modules

Modules cannot practically be re-signed after the build (they are inside the
root filesystem image). Design: the Secure Boot kernel variant uses the
kernel's own one-off module key (`CONFIG_MODULE_SIG_KEY="certs/signing_key.pem"`,
generated by Kbuild, `CONFIG_MODULE_SIG_ALL` signs at `modules_install`).
Its certificate is built into `vmlinux`, so only that exact kernel trusts it,
and the owner signs that kernel. Before enabling the fragment, a
`linux-yocto` bbappend must keep the private half out of everything that
persists:

- `do_shared_workdir:append`: delete `${STAGING_KERNEL_BUILDDIR}/certs/signing_key.pem`
  (OE copies it there and this task has an sstate setscene);
- `do_install:append` (after `modules_install` signed the modules): delete
  `${B}/certs/signing_key.pem`;
- check `kernel-devsrc`, `deploy/images` and the sstate archives for
  `signing_key.pem` in a test.

Consequence: out-of-tree modules (`module.bbclass`) can no longer be signed;
INT has none today. A rebuild regenerates a new key and relinks `vmlinux`.

## 6. Enrollment by the user (MokManager)

**A. First boot of the signed ISO (INT key not enrolled yet).**
shim cannot verify `grubx64.efi`, prints *Verification failed: (0x1A) Security
Violation* and starts MokManager:

1. *Shim UEFI key management* — press a key.
2. *Perform MOK management* → **Enroll key from disk**.
3. Choose the USB stick's EFI volume, then `INT-SecureBoot.cer`.
4. **View key 0**: check subject *INT Linux Secure Boot …* and that the SHA-1
   fingerprint matches the published one. Anything else → stop.
5. **Continue** → *Enroll the key(s)?* **Yes** → **Reboot**.

**B. From a running INT system (live or installed) with `mokutil`.**

1. `mokutil --import /path/INT-SecureBoot.cer` — choose a one-time password.
2. Reboot. *Press any key to perform MOK management* appears for about ten
   seconds; press a key (missed → repeat step 1).
3. **Enroll MOK** → **View key 0** (check the fingerprint) → **Continue** →
   **Yes** → enter the one-time password → **Reboot**.

Check: `mokutil --sb-state`, `mokutil --test-key INT-SecureBoot.cer`,
`mokutil --list-enrolled`. Removal: `mokutil --delete INT-SecureBoot.cer`
(confirmed the same way at the next boot).

## 7. Installer changes needed (not done)

`int-install-efi.sh` (not modified by this work) must, for the Secure Boot
variant:

- copy from the medium to the target ESP:
  `EFI/INT/shimx64.efi`, `EFI/INT/mmx64.efi`, `EFI/INT/grubx64.efi`, and the
  removable fallback `EFI/BOOT/BOOTX64.EFI` (= shim) with `mmx64.efi` and
  `grubx64.efi` beside it, plus `INT-SecureBoot.cer` at the ESP root;
- create the firmware entry on shim:
  `efibootmgr -c -d "$device" -p 1 -L "INT Linux" -l '\EFI\INT\shimx64.efi'`
  (GRUB must then be built with a prefix that works from both `/EFI/INT` and
  `/EFI/BOOT`, e.g. `$cmdpath`);
- stop writing a per-install `grub.cfg` with `PARTUUID`: name the partitions
  (`INT-EFI`, `INT-ROOT`) and use a fixed `root=PARTLABEL=INT-ROOT` /
  `intluks=PARTLABEL=INT-ROOT` so the menu can be embedded in the signed GRUB;
- copy the signed `bzImage` from the medium (already the case);
- offer `mokutil --import` when `mokutil --sb-state` reports Secure Boot on
  and the INT key is not enrolled (`mokutil --test-key`);
- add `mokutil` to the live image and installer `RDEPENDS`.

## 8. Implementation order (proposal)

1. Pin a Microsoft-signed shim (1b): exact package, version, sha256 and
   `sbverify --list` output of its signer, documented here.
2. `grub-efi` bbappend for a Secure Boot variant: `--sbat`, complete
   `GRUB_BUILDIN`, embedded menu without `search`.
3. Kernel variant: `int-secureboot.cfg` + module-key hygiene bbappend + test
   that no `signing_key.pem` reaches sstate/deploy/packages.
4. QEMU + OVMF with Secure Boot enforcing (`OVMF_CODE.secboot.fd` and a VARS
   file with Microsoft keys): signed ISO boots after MOK enrollment, unsigned
   kernel and unsigned module are refused, unsigned GRUB is refused.
5. Installer changes (section 7) and the same tests on the installed system.
6. Real hardware with the third-party CA enabled.

## 9. Honest list of what is not done

- No image contains shim, mokutil or a Secure Boot GRUB/kernel; Secure Boot
  must still be **disabled** to boot INT.
- `shim_16.1.bb` and `mokutil_0.7.3.bb` were written and pinned but never
  built (no BitBake run in this task). The shim build in particular may need
  compiler/linker adjustments under OE.
- No Microsoft-signed shim has been chosen or pinned yet.
- GRUB has no `.sbat`, no Secure Boot module set, and still searches other
  disks for `grub.cfg`; `grub.cfg` on the ESP is not verified.
- The initrd (live installer, LUKS unlock) is **not verified** by shim or
  GRUB. Anyone who can write the USB stick or the ESP can replace it. A
  signed Unified Kernel Image (kernel + initrd + command line in one PE,
  `uki.bbclass`) would close this; not designed in detail yet.
- The root filesystem is not verified (no dm-verity); Secure Boot here only
  protects the boot chain up to the kernel.
- The kernel fragment `int-secureboot.cfg` is not applied, the module-key
  hygiene bbappend does not exist, and `CONFIG_EFI_STUB` in the current
  live kernel has not been confirmed (`sign-boot.py` refuses non-PE kernels).
- `sign-boot.py` was tested with fake `sbsign`/`sbverify`; its ISO path was
  checked with real `xorriso`/mtools on a synthetic ISO, not on a real INT
  ISO and not booted.
- No sbsigntools or efitools recipe; no shim-review submission.
