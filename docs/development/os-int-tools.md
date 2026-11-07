# OS-INT tool set

Status on 2026-11-07: **recipes written and host-tested only. None of the
new recipes below (tor, int-osint-hardening) has been built with BitBake or
booted yet.** The packages already in the group before this change were built
into the live ISO (see `COORDINATION.md`).

`packagegroup-int-osint` (`meta-int/recipes-core/packagegroups/`) is in
`int-image-live`, so until the package feed exists both editions of the ISO
carry it.

## Tools

| Package | Purpose | Source |
|---|---|---|
| nmap | network scanner | meta-openembedded |
| tcpdump, tshark | packet capture and analysis | meta-openembedded |
| wireguard-tools, openvpn | VPN clients | meta-openembedded |
| macchanger | manual MAC address changes | meta-openembedded |
| netcat-openbsd, socat, traceroute | network utilities | meta-openembedded |
| exiftool | metadata reading and removal | meta-openembedded |
| gnupg | encryption, signatures | openembedded-core |
| cryptsetup | LUKS2 disk encryption | meta-openembedded |
| tor (+ tor-geoip) | Tor client, 0.4.9.16 | `meta-int/recipes-security/tor/` |
| int-osint-hardening | sysctl hardening + `int-privacy` | `meta-int/recipes-security/int-osint-hardening/` |

**Not included: torsocks.** It is not in the pinned layers, and its official
source (gitlab.torproject.org) could not be reached from the session that
wrote these recipes, so no tarball could be downloaded and pinned. It will
be added once a pinned official tarball is available. Tor's `torify` wrapper
needs torsocks and is therefore not installed. Applications can use the
SOCKS proxy directly (`socks5h://127.0.0.1:9050`).

## Enabled by default

**Nothing listens on the network.** No service from this group is enabled:

- `tor.service` is installed with `SYSTEMD_AUTO_ENABLE = "disable"`.
  `sudo int-privacy tor on` enables and starts it; `sudo int-privacy tor off`
  stops and disables it.
- When running, Tor only opens a SOCKS port on `127.0.0.1:9050`. It has no
  ControlPort (a commented localhost and cookie-only example is in the
  torrc). It is built without the relay and directory-authority modules, so
  it cannot be a relay, bridge, exit or directory cache. It runs as the
  `tor` system user under a hardened systemd unit: no capabilities,
  `NoNewPrivileges`, read-only system, private `/tmp` and devices, and
  `/var/lib/tor` with mode 0700.
- Things that are on by default but do not listen: the sysctl drop-in
  `/usr/lib/sysctl.d/90-int-osint.conf` and the OS-INT MAC randomisation
  link file written by the installer.

## Hardening drop-in

`90-int-osint.conf` sets `kernel.kptr_restrict=2`, `kernel.dmesg_restrict=1`,
strict reverse-path filtering (`rp_filter=1` for all, default and existing
interfaces), no accepted ICMP redirects (IPv4 and IPv6), no sent redirects,
and `net.ipv4.tcp_syncookies=1` (`CONFIG_SYN_COOKIES=y` comes from the
linux-yocto base configuration).

`kernel.yama.ptrace_scope=1` is listed with a leading `-`, so systemd-sysctl
skips it without an error: **the pinned kernel does not have Yama**. Neither
the INT fragments nor the linux-yocto standard/qemux86-64 metadata enable
`CONFIG_SECURITY_YAMA`. Enabling it needs `CONFIG_SECURITY_YAMA=y` in a
kernel fragment. That changes the kernel shared with the desktop profile, so
it must be agreed in `COORDINATION.md` first. Afterwards, remove the `-`.

Strict `rp_filter` can drop traffic on multi-homed hosts with asymmetric
routes. wg-quick sets `src_valid_mark` and keeps working. Override with
`/etc/sysctl.d/90-int-osint.conf` if needed.

## int-privacy

POSIX sh. User input is only passed as separate arguments, never evaluated.

- `int-privacy status`: whether the MAC randomisation policy
  (`/etc/systemd/network/10-int-mac-random.link`) is present, and whether the
  Tor and nftables services are enabled and active.
- `int-privacy tor on|off`: `systemctl enable|disable --now tor.service`.
  Needs root, and refuses with a clear message otherwise.
- `int-privacy clean-metadata FILE...`: checks every argument first and
  changes nothing if any is a symbolic link, a directory, missing or not a
  regular file. It then runs `exiftool -all= -overwrite_original` on the
  files (names starting with `-` are passed as `./-name`). Files are
  rewritten in place without a backup. exiftool cannot remove every kind of
  metadata, for example earlier PDF revisions.

## Tor source verification

`tor-0.4.9.16.tar.gz` was downloaded from https://dist.torproject.org/ and
matched the published `tor-0.4.9.16.tar.gz.sha256sum`
(`6180e193…6160e48`). The detached signature
(`.sha256sum.asc`, signed by fingerprints
`B74417EDDF22AC9F9E90F49142E86A2A11F48D36` and
`514102454D0A87DB0767A1EBBE6A0531C18A9179`) **was not verified**. The Tor
signing keys could not be fetched from an official source (the torproject.org
WKD hosts and keys.openpgp.org were blocked by the session's network policy). Verify the
signature before the first release build.

## Not yet done

- BitBake build of `tor` and `int-osint-hardening`, and a boot test showing
  that `tor.service` is disabled, `int-privacy status` works and the sysctl
  values are applied.
- torsocks recipe (see above).
- `CONFIG_SECURITY_YAMA=y` (see above).
