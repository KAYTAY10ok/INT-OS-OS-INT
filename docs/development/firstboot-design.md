# First owner enrollment

Development implementation, verified through real enrollment/login/sudo in the
[core VM test](validation-core-2026-11-05.md). Physical-console and repeated
power-loss qualification remain open. The core image
contains no owner account, password hash, public SSH service, or shared root
password. Root remains locked. On the trusted first-use local console, the
operator chooses an unused account name and an interactive password. Upstream
shadow `passwd` and PAM handle terminal echo, password input, and hashing. INT
does not collect a password through shell arguments, environment, configuration,
or a custom hashing implementation.

`int-firstboot.service` runs before console gettys. Their template drop-ins
require successful enrollment, so a failed enrollment does not expose a root
recovery shell. This assumes a trusted first-use console and boot media; whoever
controls that console before enrollment can become the owner. Encryption,
verified boot, graphical onboarding, and remote enrollment are later work.

## Persistent transitions

The root-owned state directory `/var/lib/int-firstboot` has mode 0700. Each
record is a root-owned regular file with mode 0600, one line containing only
the account name and numeric UID. Symbolic links and malformed records fail
closed. A process lock prevents simultaneous enrollment.

1. An unused account, group, and `/home/name` are required. Existing names and
   homes are never adopted or removed. `useradd` creates a private home, an
   expired account, `nologin` shell, and no supplementary groups.
2. `pending` records that identity. A resumed pending account must still be
   expired, use `nologin`, and lack wheel membership. `passwd` sets its password;
   it remains expired and without a login shell while that happens.
3. `committed` is atomically renamed into place and synchronized before
   activation. Its existence authorizes repeatable wheel membership, `/bin/sh`,
   and removal of expiry. A reboot during activation resumes these operations
   without resetting the password.
4. `complete` is written before removing the intermediate records. Later boots
   validate that record and leave account databases unchanged. Administrators
   can subsequently change their accounts without boot-time policy resets.

These records do not make passwd, shadow, and group updates atomic as a group.
Each component relies on upstream shadow locking and update behavior. A power
failure between `useradd` and writing `pending` can leave an orphaned account
that is still expired and uses `nologin`. Enrollment refuses to adopt it;
choose another unused name, or use separately authorized offline administrative
recovery after inspecting the account and home. No unknown account is deleted
automatically. Corruption and partial storage writes require recovery; repeated
power-loss qualification has not been performed.

## Administration and validation

The owner joins wheel only after commit. The sudo policy requires a password
for every administrative invocation (`timestamp_timeout=0`); there is no
NOPASSWD rule. Upstream sudo/PAM performs authentication. The image must retain
the `sudo` meta-package, including its policy checker and PAM dependencies,
and shadow's account commands; `shadow-base` alone is insufficient.
The INT PAM append removes the upstream common-auth empty-password exceptions
(`nullok`/`nullok_secure`). Creating or later changing an account to an empty
password must not grant login or sudo authentication through this stack.

Host tests run a copy of the production shell with a disposable account-command
backend and redirected state directory. They exercise identity collisions,
record validation, quarantine checks, ordered commit, interrupted activation,
and repeat enrollment. They never modify host accounts. These tests cannot
validate actual PAM or terminal behavior.

The disposable core VM test must enroll with a fresh in-memory random password,
prove that password never appeared in console output, connect through the real
login program as a non-root user, authenticate sudo, and shut down cleanly.
Its test-only root helper and network probes are excluded from `int-image-core`.
The retained input image stays unprovisioned; QEMU changes use a temporary disk
snapshot. No development password belongs in logs or artifacts.
