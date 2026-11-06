# Interactive launcher validation — 2026-11-06 UTC

`./scripts/int run` was exercised against a freshly built `int-image-core` in
a cloud session (4 vCPUs, no KVM, QEMU 8.2.2 TCG), driven by a scripted
"user" through the real serial console. This is a virtual-machine functional
check of the launcher and of the owner workflow, not a release or hardware
qualification.

## Build

`./scripts/int build int-image-core` on the pinned sources: all 3250 tasks
succeeded (the run resumed once after the cloud machine restarted; BitBake
reused completed tasks). Deployed artifacts used:

| Artifact | SHA-256 |
| --- | --- |
| `bzImage` (6.18.54, `-int-core1`) | `7a2df4e81ed894eee909f600911214b546402b2507bc25dd13c0944b91bbcd1d` |
| `int-image-core-qemux86-64.rootfs-20261106181756.ext4` | `c89d8a8de2b5383c80f37f356fce137481e4be92bd51bc1fc2859b15c4a34994` |

## Scenario and result

1. `./scripts/int run --reset`: owner enrollment prompt, owner `tester` with a
   random throwaway password, serial login prompt after 28 s, login,
   `id -u` = 1000, `PRETTY_NAME` = `INT Linux 0.1.0-dev (foundation)`,
   `sudo -k; sudo id -u` asked for the password and returned 0,
   `sudo poweroff`: QEMU exited 0 after 40 s.
2. `./scripts/int run` (same saved state): no enrollment prompt (the owner
   persisted), login prompt after 23 s, login, `sudo` returned 0, poweroff,
   QEMU exit 0 after 34 s.

After both boots the deployed kernel and rootfs still matched the hashes
above: the launcher only modified its private copy under
`INT_WORKDIR/run/int-image-core`.

## Not covered

The desktop launch path (`--profile desktop run`, GTK/SDL window, enrollment
on `tty0`) was not exercised here: `int-image-desktop` was not built in this
session and the session has no display. KVM acceleration was not exercised.
Firewall, networking and wrong-password behaviour are covered by the existing
`core-check` validation, not by this run.
