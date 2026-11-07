# INT: show the system summary with the INT logo once per new desktop terminal.
# Disable with:  touch ~/.config/int/no-fetch
case "$-" in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -t 1 ] && [ -z "${INT_FETCH_SHOWN:-}" ] \
        && [ ! -e "${XDG_CONFIG_HOME:-$HOME/.config}/int/no-fetch" ] && command -v fastfetch >/dev/null 2>&1; then
    INT_FETCH_SHOWN=1
    export INT_FETCH_SHOWN
    fastfetch 2>/dev/null
fi
