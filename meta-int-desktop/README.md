# Shared INT desktop layer

This development layer is shared by INT-OS and OS-INT. It adds stable Sway 1.11
with wlroots 0.19.3, foot, fuzzel, Sway's own bar and original INT configuration.
It requires the exact meta-wayland source pinned by the repository lock.

Use the separate `desktop` build profile. The profile enables Wayland/OpenGL,
keeps a distinct kernel ABI, and scopes the Mesa driver selection to QEMU. It
does not qualify physical GPUs, Xwayland, Vulkan or hardware acceleration.
The compositor runs as the logged-in user through PAM/logind. Seatd is not
auto-started and owners receive no permanent input/video group membership.

After enrolling and logging in on an active local virtual console, run
`start-int-desktop`. The wrapper validates the login session and its runtime
directory before starting a private D-Bus session. Serial/remote sessions are
not treated as proof of graphical seat access.

| Shortcut | Action |
| --- | --- |
| Super+Return | Open the terminal |
| Super+d | Open the application launcher |
| Super+1…0 | Switch workspaces |
| Super+Shift+1…0 | Move the focused window to a workspace |
| Super+h/j/k/l or arrows | Move focus |
| Super+Shift+h/j/k/l or arrows | Move a window |
| Super+f | Toggle fullscreen |
| Super+r | Resize mode; Return/Escape ends it |
| Super+Shift+c | Reload the configuration |
| Super+Shift+e | Confirm session exit |

An owner config at `~/.config/sway/config` takes precedence over the shared
`/etc/int/sway/config` (or use `XDG_CONFIG_HOME`). Foot and fuzzel receive INT
global XDG defaults while retaining their normal per-user config precedence.
The copies under `/etc/int` provide explicit configuration inputs for tests.
The status bar updates its clock every thirty seconds and ends its sleep child
when the bar closes; it adds no detached monitoring service.

This layer's build, headless session and virtual DRM/logind graphical seat pass
the recorded QEMU tests. A virtual keyboard also opens the terminal, opens the
launcher and selects an application. Those results do not qualify physical input,
mouse interaction, physical GPU rendering or performance.
Use the dated validation records for actual outcomes rather than this description.
