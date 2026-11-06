# Coordination Codex / Claude

Short, dated notes so the two agents do not edit the same files at the same
time. Codex is the lead developer (see `docs/PROJECT_SPECIFICATION.md`).
Newest entry first. Read this file and `git log origin/main` before starting.

## 2026-11-06 — Claude (cloud session, branch `claude/eager-sagan-1ul1nd`)

**Owner request:** a version the owner can test by hand as soon as possible
(target: tonight).

**Split proposed by Claude, to avoid duplicate work:**

- **Codex keeps** the signed feed / DNF guest work: `int-feed-smoke`,
  `scripts/qemu-feed-check.py`, fixtures, `int-image-feed-smoke`. Claude
  implemented the same guest test and runner in parallel; the branch now
  **adopts main's versions of all those files** (merge `995c463`).
- **Claude takes** "make INT testable by the owner": `./scripts/int run`
  (`scripts/qemu-run.py`), the French guide `ESSAYER.md`, and building/booting
  `int-image-core` in the cloud session to check them.

**Added on the branch (not yet on main), all with host tests:**

- `scripts/qemu-run.py` + `./scripts/int [--profile desktop] run [--reset]`:
  interactive QEMU on the host, on a persistent copy under
  `INT_WORKDIR/run/IMAGE` (deploy outputs never modified), user-mode network
  without port forwarding, KVM when available. Takes no lock and no container.
- `scripts/feed-check.py`: read-only signed-feed audit helper from
  `signed-feed-plan.md` (doc `feed-check.md`), rehearsed with Ubuntu tools only.
- `scripts/int`: opt-in `INT_DOCKER_NETWORK=host` (loopback-only proxies),
  `parse_known_args` so `--profile` after the command is not silently ignored,
  `feed-check` command forwarding runner options to main's runner.

**Independent confirmation from the cloud session (different machine):**
native lab `int-feed-lab-native` passed 10/10 with RPM 4.20.1/Sequoia,
GnuPG 2.5.17, createrepo_c 1.2.3, after hitting the same non-UTF-8 failure
Codex fixed with `file-native` (main's fix kept).

**Please tell Claude (via this file or the PR) before editing:**
`scripts/qemu-run.py`, `ESSAYER.md`, `scripts/feed-check.py`.
