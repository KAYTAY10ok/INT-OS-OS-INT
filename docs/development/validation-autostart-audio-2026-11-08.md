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

6. Sound playback: in a desktop terminal,
   `dd if=/dev/urandom bs=192000 count=10 | pw-cat -p -a --format s16 --rate 48000 --channels 2 -`
   returned 0 ([screenshot](evidence/audio-02-played.png)). The WAV file
   written by QEMU's audio backend holds 15.1 s at 44.1 kHz with 881 977
   non-zero samples (peak 20 328 at the default volume 0.40): the signal went
   from PipeWire through ALSA to the virtual Intel HDA card.

Not tested: real speakers or headphones, HDMI audio, microphones, volume keys,
Bluetooth (not built), PulseAudio-only applications (no pipewire-pulse yet).

## Live ISO from `5a905e1` (int-wifi, volume keys, volume segment)

Live session, blue theme ([screenshot](evidence/audio-03-volume-bar-wifi.png)):

- The status bar shows `VOL 40%` (default PipeWire sink volume).
- `int-wifi status` without a Wi-Fi card: "No Wi-Fi card found.", exit code 4.
- The volume keys could **not** be checked: QEMU's USB keyboard does not send
  the multimedia key sent through QMP (`volumeup`), the volume stayed at 0.40.
  They need a real keyboard.
- `wpctl` prints RTKit warnings (no RTKit daemon, it needs polkit); PipeWire
  runs without realtime priority. Cosmetic; not fixed.
