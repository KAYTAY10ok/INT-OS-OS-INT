# Validation: desktop autostart, INT-OS presets, PipeWire (2026-11-08)

QEMU, UEFI (OVMF), q35, TCG, 3 GB RAM, NVMe 16 GB, Intel HDA audio device
(`-device intel-hda -device hda-duplex`, WAV backend). Live ISO built from
`8ba4e95` (int-audio, PipeWire restricted to ALSA + WirePlumber). Not real
hardware.

1. Live ISO → `install`: French, US keyboard, **INT-OS**, no encryption, no AI.
2. First boot: owner account created, login on tty1. **No command typed**: the
   theme chooser appeared by itself (autostart from `/etc/profile.d`)
   ([screenshot](evidence/autostart-01-theme-without-command.png)).
3. Application chooser with INT-OS defaults: desktop-tools and audio `[x]`.
   Enter kept the defaults; plan removed packagegroup-int-osint, the cyber,
   opsec, terminal and dev packages ([screenshot](evidence/apps-int-os-01-plan.png)),
   confirmed, sudo password.
4. In the desktop: `systemctl --user is-active` reports the PipeWire socket and
   service active; `wpctl status` lists WirePlumber, device "Audio interne"
   [alsa], sink and source "Audio interne Stéréo analogique"
   ([screenshot](evidence/audio-01-wpctl.png)). wpctl prints RTKit warnings
   (no RTKit daemon: PipeWire runs without realtime priority).
5. Reboot, login: the desktop starts directly (no questions again);
   `int-apps list` shows only desktop-tools and audio installed; `rpm -q`
   shows nmap and gnupg removed, grim and int-audio present; marker = 0
   ([screenshot](evidence/apps-int-os-02-after-reboot.png)).

Sound playback into the virtual card: see the result below (pending at the
time of writing).
