# INT: start the desktop right after logging in on the first console (tty1)
# of an installed system. Turn it off or on with:  int-session autostart off|on
# Other consoles (Ctrl+Alt+F2...) always stay plain text consoles.
case "$-" in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${INT_AUTOSTARTED:-}" ] && [ -f /etc/int/install.conf ] \
        && [ "$(tty 2>/dev/null)" = /dev/tty1 ] && [ "$(id -u)" -ge 1000 ] \
        && [ ! -e "${XDG_CONFIG_HOME:-$HOME/.config}/int/no-autostart" ] && command -v start-int-desktop >/dev/null 2>&1; then
    INT_AUTOSTARTED=1
    export INT_AUTOSTARTED
    # Not exec: if the desktop cannot start, the text console stays usable.
    start-int-desktop || printf '%s\n' "start-int-desktop failed; you are on the text console." >&2
fi
