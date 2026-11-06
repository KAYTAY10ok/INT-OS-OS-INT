# INT baseline firewall

Status: the Phase 2 development image passes the IPv4 packet controls, reload,
invalid-policy network startup gate and recovery in the [core VM test](validation-core-2026-11-05.md).
Physical-network and IPv6 runtime qualification remain open.

The pinned upstream nftables 1.1.6 recipe comes from meta-networking. INT enables
upstream's `nftables.service` and installs a systemd drop-in; there is one policy
manager, no polling daemon, and no second firewall service. Python bindings and
interactive line editing are omitted from this baseline package.

## Policy and ownership

`/etc/nftables/rules/main.nft` owns only the `inet int_filter` table. Input and
forward chains default to drop; output defaults to accept. Loopback and replies
to established or related flows are allowed. No new inbound TCP connection is
opened by default. DHCPv4/v6 replies, IPv4 diagnostic/errors, IPv6 errors,
neighbour/router discovery, and multicast listener messages are allowed. Local
link ICMPv6 discovery and listener messages require their appropriate hop limit.

The configuration does not claim application confinement, anonymity, egress
filtering, protection from a hostile local root, protection from DHCP spoofing,
or denial-of-service resistance. Output accept permits applications to initiate
connections. An active listener is still reachable through loopback.

The entire file is submitted as one nft transaction. `add table` is idempotent;
the following `flush table inet int_filter` replaces rules only inside the
reserved INT table. There is no global `flush ruleset`. Reloading the file twice
must reproduce the same policy without duplicate rules. Invalid transactions
must leave the currently installed policy intact. Other tables remain owned by
their creators. Administrators must keep custom tables outside `int_filter`.

The service drop-in replaces upstream's global start/reload flush commands with
`nft -f /etc/nftables/rules/main.nft`. It clears upstream's stop command: stopping
the unit leaves the installed rules active. Removing the INT table therefore
requires an explicit administrative action. Systemd orders the upstream unit
before `network-pre.target` and enables it through `sysinit.target`.

The `nftables` package also owns
`systemd-networkd.service.d/10-int-firewall.conf`, which requires and orders
`nftables.service` before networkd. A failed initial policy load therefore blocks
networkd activation. INT clears upstream's `ConditionPathExists` condition so a
missing policy fails `nft -f` rather than silently skipping firewall startup.
An invalid reload leaves the previously committed policy active. This ordering
does not audit kernel/firmware traffic or unrelated processes that configure
interfaces without networkd; it is not a promise that every possible network
path is closed.

## Kernel and package requirements

The initial Phase 1 kernel had `NF_TABLES` and `VETH` disabled. Installing only
userspace nftables cannot fix that kernel. Phase 2 requires `NF_TABLES`,
`NF_TABLES_INET`, `NF_CONNTRACK`, and `NFT_CT`; normal INET, IPV6, NETFILTER, and
NET_NS support already exists. Conntrack selects IPv4/IPv6 defragmentation
support. Comparison, payload, metadata, set lookup, and filter-chain expressions
are built into `nf_tables` in this kernel. This policy uses no optional counter,
NAT, reject, logging, or rate-limit expression.

The generated Phase 2 configuration currently has `NF_TABLES=y`,
`NF_TABLES_INET=y`, `NF_CONNTRACK=m`, `NFT_CT=m`, and `VETH=m`. Thus the image needs
`nftables`, `kernel-module-nft-ct`, `kernel-module-nf-conntrack`, and their resolved
kernel/library dependencies. The nft userspace package alone does not supply
these modules. The disposable test image additionally needs
`kernel-module-veth`, `iproute2`, and the test-only C helper. No full
kernel-module bundle is needed.

No explicit `ExecStartPre=modprobe nft_ct` is added. The kernel's nft expression
lookup requests `nft-expr-<family>-ct` and then the generic `nft-expr-ct` alias;
`nft_ct` exports that alias. The existing development image uses kmod's modprobe
through `/usr/sbin/modprobe`, not the BusyBox alternative. Kernel-module package
post-install dependency metadata and matching kernel ABI are prerequisites for
this standard autoload path. The first real policy load in the Phase 2 VM must
verify it succeeds from the boot state; source inspection alone is not runtime
proof. If any module cannot load, nft fails and networkd remains gated by the
service dependency.

## Guest-only test contract

`firewall-check` and compiled `int-net-probe` must be installed in the same
libexec directory. The helper builds with the normal `${CC}`, `${CPPFLAGS}`,
`${CFLAGS}`, and `${LDFLAGS}`, using libc only. Its interface is:

```text
int-net-probe server IPv4 PORT READYFILE DEADLINE_MS
int-net-probe client IPv4 PORT TIMEOUT_MS [SOURCE_PORT]
```

A server port of zero chooses an ephemeral port, written to a newly created
readiness file only after listening succeeds. A client must receive an exact
test token: exit 0 means success, 2 means its explicit deadline expired, and 1
means another error. Connection refusal is an error, not evidence of a firewall
drop. Numeric literal addresses avoid DNS or discovery. Server lifetime and
client connect/receive operations have explicit monotonic deadlines.

Run the test only inside the disposable core smoke VM as root. It creates an
isolated network namespace and a veth pair in the reserved 198.18.0.0/30 test
range, with no default route. Servers bind only to loopback or the root-side
test veth address. No host port, physical interface, external destination, or
public listener is involved.

The test verifies loopback success, a timed-out new inbound TCP connection, a
successful connection after a narrowly scoped temporary accept rule, and a
second timeout after removing that rule. Distinct source ports prevent a prior
established conntrack flow from satisfying the final check. It also reloads the
stock service twice, submits an invalid transaction, and checks that an unrelated
test-owned table survives unchanged. Traps remove only its tagged rule, table,
namespace, links, process IDs, and temporary directory.

These checks establish only the tested IPv4 paths and reload behaviour. They do
not validate every permitted ICMP/DHCP message, IPv6 runtime traffic, forwarding
between real machines, all concurrent firewall managers, or a complete OPSEC
profile. Record actual VM results and serial logs separately.
