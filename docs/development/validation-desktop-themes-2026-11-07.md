# Desktop themes validation — 2026-11-07 UTC

Live ISO built from `main` (6,117 tasks) with `int-theme`, generated
wallpapers, the INT ASCII logo (fastfetch), `int-dashboard` and the updated
Sway session. Tested in UEFI QEMU (TCG, std VGA, USB keyboard/tablet), live
session, scripted keystrokes and screenshots:

1. `start-int-desktop` on first start listed the five presets and asked for
   one ([chooser](evidence/desktop-theme-chooser-2026-11-07.png)).
2. Choosing `anime` gave the generated sakura wallpaper with INT letters and
   pink accents on the bar ([desktop](evidence/desktop-anime-2026-11-07.png)).
3. Super+Return opened a translucent foot terminal showing fastfetch with the
   large INT logo and INT LINUX caption, OS/kernel/Sway/foot details and the
   palette ([fetch](evidence/desktop-fetch-int-logo-2026-11-07.png)).
4. Super+i opened the floating translucent dashboard with live CPU, RAM,
   disk, network and uptime ([dashboard](evidence/desktop-dashboard-2026-11-07.png)).
5. `int-ai mets le theme bleu` → `{"action":"theme.set","args":{"name":"blue"}}`
   → "Theme applied: blue": wallpaper, borders and bar switched live; a new
   terminal used the blue palette
   ([int-ai theme switch](evidence/desktop-int-ai-theme-blue-2026-11-07.png)).

Limits: already-open terminals keep their colours until reopened (foot does
not reload its config); no blur or rounded window corners on Sway (Hyprland
pending); no temperatures in QEMU; the dashboard bar glyphs render as blocks;
no GPU acceleration; real displays and HiDPI untested; light/pink/dark
presets were applied in host tests but not screenshotted in the guest.
