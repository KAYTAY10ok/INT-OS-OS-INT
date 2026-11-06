# INT Linux

INT Linux is an independent distribution built from upstream sources with
Yocto/OpenEmbedded. INT-OS and OS-INT will share one foundation and one desktop.

The shared console core now builds with first-owner enrollment and a default
firewall. Its disposable VM test passes real enrollment, login, password-authenticated
sudo, packet filtering, network recovery and clean shutdown. See the
[core validation record](docs/development/validation-core-2026-11-05.md) for exact
artifacts, scope and limitations. The earlier [minimal foundation](docs/development/validation-2026-11-05.md)
is independently preserved.
The shared Sway desktop prototype also passes headless and Virtio VGA graphical
VM tests with a real user-owned terminal, keyboard shortcuts and launcher selection. See the
[graphics validation record](docs/development/validation-graphics-2026-11-06.md).
Physical keyboards, mice and display hardware remain unqualified.
Installer, signed feeds, complete security profiles and release images remain
future work in the [roadmap](ROADMAP.md).

```sh
./scripts/int bootstrap
./scripts/int builder
./scripts/int configure
./scripts/int check
./scripts/int build int-image-core-smoke
./scripts/int core-check
```

Read [BUILDING.md](BUILDING.md) before building. Sources, caches, images and logs
live outside this checkout, by default in `../int-linux-work`.

Use `int-image-core` for the console image without test helpers. It asks for the
first owner's name and password on the local console. Root stays locked and no
SSH server or installer is included. The core smoke runner creates an ephemeral
test owner and powers the guest off; its credential is never embedded or retained.

- [Architecture and selected decisions](ARCHITECTURE.md)
- [Security assumptions](THREAT_MODEL.md)
- [Requirement status](docs/development/requirements.md)
- [Master specification](docs/PROJECT_SPECIFICATION.md)
