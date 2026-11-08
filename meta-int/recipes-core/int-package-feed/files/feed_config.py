"""Build-time renderer for an explicitly pinned INT repository."""
import re
from urllib.parse import urlsplit

KEY_PATH = "/etc/pki/rpm-gpg/INT-PACKAGE-FEED.asc"

def repository(baseurl, fingerprint):
    if not re.fullmatch(r"[0-9A-F]{40}", fingerprint):
        raise ValueError("A full uppercase primary fingerprint is required")
    # Keep INI, RPM variable and shell interpolation out of the address.
    if not re.fullmatch(r"https://[A-Za-z0-9._:/%~-]+", baseurl):
        raise ValueError("Use a literal HTTPS repository URL without credentials, query or variables")
    url = urlsplit(baseurl)
    if not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Invalid HTTPS repository address")
    if url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError("Invalid port")
    return ("# INT primary fingerprint: " + fingerprint + "\n"
            "[int-packages]\nname=INT signed packages\nbaseurl=" + baseurl + "\n"
            "enabled=1\ngpgcheck=1\nrepo_gpgcheck=1\n"
            "skip_if_unavailable=0\nsslverify=1\ngpgkey=file://" + KEY_PATH + "\n")


def validate_key_listing(listing, fingerprint, now):
    primary = 0
    signer = False
    awaiting = False
    primary_fingerprint = None
    for line in listing.splitlines():
        fields = line.split(":")
        kind = fields[0]
        if kind in ("sec", "ssb"):
            raise ValueError("Private key material is forbidden")
        if kind in ("pub", "sub"):
            if len(fields) < 12 or fields[1] in ("r", "e", "d", "i"):
                raise ValueError("Invalid, revoked, disabled or expired key")
            if not fields[5].isdigit() or int(fields[5]) > now:
                raise ValueError("Invalid key creation time")
            if fields[6] and (not fields[6].isdigit() or int(fields[6]) <= now):
                raise ValueError("Expired key")
            signer = signer or "s" in fields[11]
            if kind == "pub":
                primary += 1
                awaiting = True
        elif kind == "fpr" and awaiting:
            if len(fields) < 10:
                raise ValueError("Missing primary fingerprint")
            primary_fingerprint = fields[9]
            awaiting = False
    if not signer or primary != 1 or awaiting or primary_fingerprint != fingerprint:
        raise ValueError("Key material does not contain exactly the pinned primary")
