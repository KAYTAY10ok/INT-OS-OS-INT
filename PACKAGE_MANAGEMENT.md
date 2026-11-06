# Package management

The first build selects Yocto's `package_rpm` backend. All target packages are
built from upstream sources and packaged by OE-Core; Ubuntu is used only for host
build tools. The minimal image does not install DNF or a foreign package feed.

Next validate DNF with a small local INT feed: dependency resolution, install and
remove behavior, package/metadata signatures, unknown-key and tamper rejection,
version compatibility, interrupted updates and recovery. Define key custody,
rotation and support policy before operating a repository. Package generation is
not a signed or supported repository.

Inspection found that the existing native RPM build lacks OpenPGP support.
Digest checks alone cannot qualify package signatures. The
[signed-feed plan](docs/development/signed-feed-plan.md) records the required
Sequoia backend, test-only key handling, metadata/package rejection cases and
production signing limitations. Neither development core image installs a DNF
client or claims verified updates.

An isolated `feed` build profile selects OpenPGP-capable native and target RPM.
Its configuration is separate from the known-good images; selecting a backend
does not establish that it builds or verifies signatures. Actual signing,
tamper rejection, update and recovery tests are still open.

An eventual `int-pkg` can wrap that mature backend after its semantics are tested.
Do not create a new dependency solver or claim rollback without an implemented
and tested transaction/snapshot model. IPK trades footprint against the richer
RPM/DNF desktop workflow; image-based updates trade atomicity against mutable
application management. RPM/DNF is the chosen prototype, not a claim of measured
footprint or complete update safety.
