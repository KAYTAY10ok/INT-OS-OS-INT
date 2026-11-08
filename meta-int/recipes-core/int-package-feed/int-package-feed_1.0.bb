SUMMARY = "Pinned INT package repository configuration and public trust anchor"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
INT_FEED_BASEURL ?= ""
INT_FEED_FINGERPRINT ?= ""
INT_FEED_PUBLIC_KEY_URI ?= ""
SRC_URI = "file://feed_config.py ${INT_FEED_PUBLIC_KEY_URI}"
S = "${UNPACKDIR}"
inherit allarch
DEPENDS = "gnupg-native"
RDEPENDS:${PN} = "dnf rpm gnupg ca-certificates"

python __anonymous() {
    if not all(d.getVar(v) for v in ("INT_FEED_BASEURL", "INT_FEED_FINGERPRINT", "INT_FEED_PUBLIC_KEY_URI")):
        raise bb.parse.SkipRecipe("Set the explicit repository address, fingerprint and public key URI")
    uri = d.getVar("INT_FEED_PUBLIC_KEY_URI")
    if not uri.startswith("file://") or any(c.isspace() for c in uri) or ";" in uri:
        bb.fatal("INT_FEED_PUBLIC_KEY_URI must be one local file:// URI")
}

python do_install() {
    import importlib.util
    import os
    import pathlib
    import subprocess
    import tempfile
    import time
    source = pathlib.Path(d.getVar("UNPACKDIR"))
    spec = importlib.util.spec_from_file_location("int_feed_config", source / "feed_config.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    fingerprint = d.getVar("INT_FEED_FINGERPRINT")
    config = helper.repository(d.getVar("INT_FEED_BASEURL"), fingerprint)
    # Fetcher resolves the local key and participates in BitBake checksums.
    fetcher = bb.fetch2.Fetch([d.getVar("INT_FEED_PUBLIC_KEY_URI")], d)
    key = pathlib.Path(fetcher.localpath(d.getVar("INT_FEED_PUBLIC_KEY_URI")))
    if key.is_symlink() or not key.is_file() or not 0 < key.stat().st_size <= 65536:
        bb.fatal("A bounded regular public key file is required")
    raw = key.read_bytes()
    if not raw.startswith(b"-----BEGIN PGP PUBLIC KEY BLOCK-----") or raw.count(b"-----BEGIN PGP ") != 1 or not raw.rstrip().endswith(b"-----END PGP PUBLIC KEY BLOCK-----"):
        bb.fatal("Supply exactly one ASCII-armored public key block, never a private key")
    with tempfile.TemporaryDirectory(prefix="int-feed-key-") as home:
        result = subprocess.run([d.getVar("STAGING_BINDIR_NATIVE") + "/gpg", "--batch", "--no-options", "--homedir", home, "--with-colons", "--show-keys"], input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            bb.fatal("Cannot parse the supplied public key")
        helper.validate_key_listing(result.stdout.decode("utf-8"), fingerprint, int(time.time()))
    dest = pathlib.Path(d.getVar("D"))
    repo = dest / "etc/yum.repos.d/int-packages.repo"
    public = dest / helper.KEY_PATH.lstrip("/")
    repo.parent.mkdir(parents=True, exist_ok=True)
    public.parent.mkdir(parents=True, exist_ok=True)
    repo.write_text(config)
    public.write_bytes(raw)
    repo.chmod(0o644)
    public.chmod(0o644)
}
FILES:${PN} = "${sysconfdir}/yum.repos.d/int-packages.repo ${sysconfdir}/pki/rpm-gpg/INT-PACKAGE-FEED.asc"
CONFFILES:${PN} = "${sysconfdir}/yum.repos.d/int-packages.repo"
