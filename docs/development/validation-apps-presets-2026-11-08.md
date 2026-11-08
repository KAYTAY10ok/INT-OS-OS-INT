# Validation: application presets at the first desktop start (2026-11-08)

QEMU, UEFI (OVMF), q35, TCG, 3 GB RAM, NVMe disk 16 GB, live ISO built from
`3c0873d` (int-apps, package-management). Not real hardware.

1. Live ISO → `install`: French, US keyboard, **OS-INT**, no encryption, no
   AI, NVMe disk. Installation succeeded; firmware entry "INT Linux" created.
2. First boot of the installed system: owner account created, login,
   `start-int-desktop`.
3. Theme chooser, then the application chooser: OS-INT defaults cyber, opsec,
   terminal, desktop-tools marked `[x]`; feed presets marked as needing the
   INT feed. Answer `1 2 3 5` (cyber, opsec, terminal, dev): plan shown
   "À retirer : grim slurp wl-clipboard mako swaylock swayidle brightnessctl",
   confirmed with `o`, sudo asked for the password
   ([screenshot](evidence/apps-01-chooser-plan.png)).
4. The desktop started afterwards ([screenshot](evidence/apps-02-desktop-after.png)).
5. Reboot, login: `int-apps list` shows cyber/opsec/terminal/dev installed,
   desktop-tools not installed; `rpm -q` shows grim absent, nmap, gdb,
   cryptsetup, int-apps present; `~/.config/int/apps-chosen` = 0
   ([screenshot](evidence/apps-03-reboot-verify.png)).

Found and fixed afterwards: the feed presets printed "(dépôt INT requis)"
twice (`0999fce`). Not tested here: adding a feed preset with a configured
repository (no INT feed exists), int-ai `apps.*` actions in the guest, the
audio preset (built after this run).
