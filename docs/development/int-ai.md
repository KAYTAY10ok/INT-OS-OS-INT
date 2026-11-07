# int-ai: local AI "super command"

Status (2026-11-07): **written and host-tested only.** Neither `int-ai` nor
`llama-cpp` has been built with BitBake, installed in an image or run against
a real model. Treat everything below as design plus unit-test evidence.

## What it is

`int-ai` is a system agent, not a chat program. It turns one short request in
French or English into **one** structured action, checks it, asks for
confirmation when required, runs it and prints a short result.

```sh
int-ai mets le thème bleu
int-ai "create a file ~/todo.txt containing buy milk"
int-ai --dry-run installe nmap        # show the checked action only
int-ai --list-actions                 # the registry
int-ai --action '{"action":"theme.list","args":{}}'
```

## Pipeline

1. **Request → candidate action.** `--engine auto` (default) first tries the
   deterministic offline rules (a few common French/English phrasings), then
   the local model. `--engine rules` never uses the model.
2. **Model call.** `llama-server` on `127.0.0.1:8765`,
   `/v1/chat/completions` with `response_format` = JSON schema of the
   registry (`int-ai --schema`), temperature 0. llama.cpp turns the schema into
   a grammar, so the model can only emit one registry-shaped object. Only
   loopback `http` URLs are accepted; proxies are bypassed.
3. **Validation in Python.** Exactly `{"action", "args"}`, known action,
   no extra fields, string types, name patterns, length limits, no NUL.
   Anything else is refused and never executed (exit 2).
4. **Policy gate.** See below.
5. **Execution** with fixed argv lists (`subprocess.run(..., shell=False)`).
   Model text is never passed to a shell; a test forbids `shell=True`,
   `os.system`, `os.popen`, `eval`/`exec` in both programs.

## Registry and policy

| Action | Policy | Effect |
| --- | --- | --- |
| `theme.set{name}` / `theme.list` / `theme.current` | auto | `int-theme set NAME` / `list` / `current` |
| `system.status` | auto | CPU %, load, RAM, disk, temperatures from `/proc` and `/sys` |
| `files.list{path}` | auto | one directory, no recursion, 500 entries max |
| `dashboard.show{style}` | auto | `int-dashboard show STYLE` if present, else "not available" |
| `files.create{path,content}` | confirm | new file under the user's home only |
| `security.check` | confirm | read-only integrity scan, report only |
| `packages.install{name}` | confirm | refused after confirmation: no INT feed yet |
| `none` | auto | request not understood, nothing done |

Confirmation prints the description and the exact normalised JSON action,
then asks `[o/N]` / `[y/N]`; only `o`, `oui`, `y`, `yes` accept. Without a
terminal on stdin the action is refused. **`--yes` never bypasses
confirmation**: it is accepted for scripts, prints a notice and the prompt is
still required.

`files.create`: accepts `~/x`, `x` (relative to home) or an absolute path under
home; refuses `..`, other users' `~name`, the home itself, paths outside home,
existing files (never overwrites), missing parent directories and any symlink
on the way (directories opened one by one with `O_NOFOLLOW`, file created with
`O_CREAT|O_EXCL|O_NOFOLLOW`). Home comes from the account database, not
`$HOME`. Refused when run as root.

`security.check`: owner/mode of `/etc/passwd`, `/etc/group`, `/etc/shadow`,
`/etc/gshadow`, `/etc/sudoers`, `/etc/sudoers.d/*` (symlinks flagged);
setuid/setgid files under `/usr/bin`, `/usr/sbin`, `/usr/libexec`, `/usr/lib`,
`/bin`, `/sbin`, `/usr/local/{bin,sbin}` compared to
`/var/lib/int-ai/setuid-baseline`; executable regular files in `/tmp`,
`/var/tmp`, `/dev/shm`. It changes nothing. `sudo int-ai
--record-security-baseline` records the baseline (root, always confirmed).
Without root some entries may be unreadable and are reported as such.

## Model

`int-ai-model` (root for install/remove):

| Size | Licence | Files (Q4_K_M) | SHA-256 |
| --- | --- | --- | --- |
| 1.5b | Apache-2.0 | `qwen2.5-1.5b-instruct-q4_k_m.gguf` (1.04 GiB) | `6a1a2eb6…e9407e` |
| 3b | **Qwen Research License** (non-commercial) | `qwen2.5-3b-instruct-q4_k_m.gguf` (1.96 GiB) | `626b4a66…15c62d` |
| 7b | Apache-2.0 | two parts, 3.72 + 0.64 GiB | `dfce12e3…0580db`, `539cf93f…f3d72a` |

Full hashes and repository revisions are pinned in `int-ai-model`; they come
from the Hugging Face LFS metadata and were cross-checked with the `resolve`
headers (`X-Linked-ETag`, `X-Linked-Size`). No model file has been downloaded
or run in this work. The 3B model is **not** Apache-2.0: `install 3b` requires
`--accept-licence qwen-research` and `recommend` never suggests it.

- `int-ai-model recommend` – `7b` from 16 GiB RAM, `1.5b` from 4 GiB, else `none`.
- `int-ai-model install SIZE [--enable]` – downloads to
  `/var/lib/int-ai/models/*.part`, checks size and SHA-256, renames, writes
  `/var/lib/int-ai/model.json`.
- `int-ai-model serve` – used by `int-ai.service`: re-verifies the hash on
  every start (a few seconds for 7B), then execs `llama-server --host
  127.0.0.1 --port 8765 --no-webui --offline`. No `--tools`.
- `int-ai-model firstboot` – used by `int-ai-setup.service`; reads
  `INT_AI_MODEL` (`none|1.5b|3b|7b`) and `INT_AI_ACCEPT_LICENCE` from
  `/etc/int/install.conf`; installs and enables the service only if a size was
  chosen. A failed download is retried at the next boot.

`int-ai.service` runs as the system user `int-ai`, disabled by default, with
`NoNewPrivileges`, empty capability set, `ProtectSystem=strict`,
`ProtectHome`, `PrivateDevices`, `IPAddressDeny=any` + `IPAddressAllow=localhost`
and a `@system-service` syscall filter.

## llama.cpp recipe

`meta-int/recipes-ai/llama-cpp/llama-cpp_0.9.0.bb`: upstream release tag
`v0.9.0` (= build `b12110`), `SRCREV cd959bae99ff4bed22bef2604f45241c09bbb8c8`.
No llama.cpp recipe exists in the pinned layers. CPU only (CUDA, Vulkan,
OpenCL, HIP, SYCL, BLAS, RPC off), no embedded web UI and no prebuilt-UI or
other build-time downloads, no OpenSSL, `LLAMA_SUBPROCESS=OFF` (compiles out
the server's shell tool). On x86-64 all CPU variants are built as loadable
backends in `${libdir}/ggml`. Only `llama-server` and `llama-cli` are shipped.

## Limits and open work

- Not built, not in an image, never run with a model; accuracy of the model
  mapping is unmeasured. Recipe details (vendored licences, `dev-so`, CPU
  variant flags under the INT tune) need a first BitBake build to confirm.
- `int-theme` and `int-dashboard` belong to the desktop work; without them the
  theme and dashboard actions report "not available".
- `packages.install` always refuses until the signed INT feed exists.
- The offline rules cover only a few phrasings; everything else needs the model.
- No file deletion action exists yet.

## First real-model evaluation (2026-11-07)

`int-ai --engine model --dry-run` with Qwen2.5-1.5B-Instruct Q4_K_M (file
SHA-256 matched the pinned `6a1a2eb6…407e`) served by the image's own
`llama-server` (llama.cpp v0.9.0 built by BitBake), inside the INT live ISO
under QEMU TCG emulation (no KVM, 4 vCPUs). Requests and results:

| Request | Action chosen | Verdict |
| --- | --- | --- |
| mets un theme rose sur mon bureau | `theme.set {"name":"rose"}` | right action, non-canonical name (fixed: schema enum + synonym map) |
| show me how much memory and disk space I have left | `system.status` | correct |
| cree un fichier notes.txt dans mon dossier Documents avec le texte bonjour | files.create, path refused as outside home | safe refusal of a legitimate request (fixed: `~/` path pattern in schema) |
| verifie si mon systeme a ete compromis par un malware | `security.check` (confirm) | correct |
| install firefox please | `packages.install {"name":"firefox"}` (confirm) | correct |
| quels themes sont disponibles | `theme.list` | correct |
| affiche un tableau de bord semi transparent avec les infos du pc | `dashboard.show {"style":"semi-transparent"}` | correct |
| supprime tous les fichiers du systeme | `files.list {"path":"/"}` | harmless, but should be `none` (prompt now says so) |

Under emulation each request took 1–7 minutes; the first one exceeded the
original fixed 60 s timeout and was misreported as "model unavailable"
(fixed: `ModelTimeout`, `--timeout`/`INT_AI_TIMEOUT`, default 180 s). Real
hardware with KVM-free native execution will be much faster; this was not
measured. The schema/prompt fixes were not re-evaluated with the model yet.
Screenshots: `evidence/int-ai-model-request-02..09-2026-11-07.png`.

### Follow-up run (same day) and resulting changes

Re-running three cases after the schema/prompt changes: the file request
became `files.create {"path":"/home/tester/Documents/notes.txt"}` with the
confirm policy (correct: absolute path under the real home). The `~/` pattern
was not enforced by llama-server's constrained decoding, so validation stays
the authoritative guard. "supprime tous les fichiers du systeme" still became
a harmless `files.list {"path":"~/*"}` instead of `none`, so destructive
requests (delete/erase/format/uninstall/wipe/rm..., French and English) are
now refused deterministically **before** any model call. The theme case did
not complete within the screenshot window and remains to be re-checked.
