# Installing repository trust on INT systems

`int-package-feed` is an opt-in package that delivers the repository address
and its public trust anchor to an installed image. It does not sign packages,
operate a server, publish a feed, or enable `int-ai` installations by itself.
No production URL/key is configured or included by default.

The integration contract with `int-apps` is:

- `/etc/yum.repos.d/int-packages.repo`: enabled HTTPS base URL, package and
  metadata signature checking enabled, TLS verification enabled, failure
  rather than skipping an unavailable repository.
- `/etc/pki/rpm-gpg/INT-PACKAGE-FEED.asc`: only the independently pinned public
  key, installed by the package. The same key signs metadata and packages in
  this first contract. No keyserver or remote key URL supplies the trust anchor.

A release configuration (in private build settings or a separate release layer)
can opt in with:

```bitbake
require conf/distro/include/int-package-feed.inc
INT_FEED_BASEURL = "https://YOUR-REPOSITORY/int/x86_64"
INT_FEED_FINGERPRINT = "FULL_40_CHARACTER_UPPERCASE_PRIMARY_FINGERPRINT"
INT_FEED_PUBLIC_KEY_URI = "file://release-feed-public.asc"
IMAGE_INSTALL:append:pn-int-image-desktop = " int-package-feed"
IMAGE_FEATURES:append:pn-int-image-desktop = " package-management"
```

Place that **public** armored key in the release layer's FILESPATH. Never pass
private keys or passphrases into BitBake. The recipe is skipped when settings
are missing, so an image opting into it cannot silently ship a placeholder
repository. Its build validates the address and supplied key fingerprint,
validity dates, and rejects private-key material. The opt-in include selects
Sequoia for native/target RPM. The two image overrides retain the RPM database
and install DNF and the trust package on that image only. Replace the image
name for another intended image; never apply these image settings globally to
installer/unlock initramfs recipes. Existing profiles remain opt-in.

The fingerprint must be obtained independently from the release authority.
A build-time key validity check is not a revocation or rotation service;
cached packages and installed keys still need an explicit lifecycle policy.
Keep old signing keys available for recovery as required by that policy.
A root administrator can change the repository file; this mechanism does not
claim to defend against a compromised root account.

## Before enabling for users

The actual HTTPS endpoint, signed packages and metadata, release key custody,
update/revocation policy and transport tests are still required. Install and
upgrade in a fresh VM with the public key in the image, verify the successful
path and the rejection cases against the real release repository. The present
VM results use disposable local fixtures only. Do not point production systems
at those fixtures or promote their test keys.

`int-apps` already reads enabled repository files in this directory; it need
not write keys or repository configuration. `int-ai packages.install` remains
explicitly unavailable until the repository is usable and its confirmed
installation path is integrated by the owner of `int-ai`. No changes to
`int-apps`, `start-int-desktop` or `int-ai` are made by this component.

The repository options govern repository packages. `localpkg_gpgcheck` is a
DNF main option, not a repository option: local-file installs need their own
explicit global policy and are not configured by this package.

## Build evidence (2026-11-08)

The recipe built successfully with the locked OE tools in the feed profile,
using the disposable public key from `resume-20261108` and an example.invalid
HTTPS URL. 3,269 tasks, 3,253 already satisfied, no failures. Log:
`/workspace/int-linux-work/feed-client-build-final.log`, SHA-256
`c7c6ead28b8b394f2b026e660d68c4aedbdc176dd7a929b04624f0ceeedab346`.
The resulting laboratory RPM SHA-256 is
`603e1e6757e4d1d01b2ca33c406df9de4ee4e8f748252be5ec63b658c2d0fba6`.
Native bsdtar extracted and confirmed its actual repository file: only the
specified HTTPS URL, enabled gpgcheck/repo_gpgcheck/sslverify and the local
public key path. The package was not installed in a guest or production
image. The tests exercise configuration injection rejection and key-listing
identity/validity; they do not qualify a real HTTPS package service.

A follow-up build also passed after rejecting GnuPG's disabled-key capability
flag (`D`), in addition to disabled validity records: 3,269 tasks, 3,252
already satisfied. Log `/workspace/int-linux-work/feed-client-disabled-key-build.log`
SHA-256 `b1c6021d1bcc7e3eace0d4ab34096ee74881e7d4ffd0162f7cbcf110736b9268`.
The valid-key output RPM hash above is unchanged; the added rejection path
is covered by the key-listing test.
