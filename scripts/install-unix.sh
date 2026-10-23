#!/bin/sh
# Install fortiauto as a per-user background service on Linux (systemd --user)
# or macOS (launchd). No root, no pip, nothing installed into your Python.
#
#   sh scripts/install-unix.sh            install / update
#   sh scripts/install-unix.sh uninstall  remove (keeps credentials/config)
set -eu

APP="$HOME/.local/share/fortiauto/app"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || true)"

if [ "${1:-}" = "uninstall" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        launchctl unload "$HOME/Library/LaunchAgents/com.fortiauto.plist" 2>/dev/null || true
        rm -f "$HOME/Library/LaunchAgents/com.fortiauto.plist"
    else
        systemctl --user disable --now fortiauto.service 2>/dev/null || true
        rm -f "$HOME/.config/systemd/user/fortiauto.service"
        systemctl --user daemon-reload 2>/dev/null || true
    fi
    rm -rf "$HOME/.local/share/fortiauto"
    echo "fortiauto uninstalled (credentials/config left in ~/.config/fortiauto)"
    exit 0
fi

[ -n "$PY" ] || { echo "python3 not found" >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "need Python 3.9+" >&2; exit 1; }

mkdir -p "$APP"
rm -rf "$APP/fortiauto"
cp -R "$REPO/fortiauto" "$APP/"
echo "copied to $APP/fortiauto"

if [ "$(uname)" = "Darwin" ]; then
    PLIST="$HOME/Library/LaunchAgents/com.fortiauto.plist"
    mkdir -p "$(dirname "$PLIST")"
    sed -e "s#@PYTHON@#$PY#g" -e "s#@APP@#$APP#g" "$REPO/scripts/com.fortiauto.plist" > "$PLIST"
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load -w "$PLIST"
    echo "launchd agent loaded: $PLIST"
else
    UNIT="$HOME/.config/systemd/user/fortiauto.service"
    mkdir -p "$(dirname "$UNIT")"
    sed -e "s#@PYTHON@#$PY#g" -e "s#@APP@#$APP#g" "$REPO/scripts/fortiauto.service" > "$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --now fortiauto.service
    echo "systemd user service enabled: $UNIT"
    echo "tip: 'loginctl enable-linger $(id -un)' keeps it running when you're logged out"
fi

echo
if [ -t 0 ]; then
    printf "Save your portal username/password now? [Y/n] "
    read -r ans || ans=n
    case "$ans" in
        [nN]*) ;;
        *) (cd "$APP" && "$PY" -S -m fortiauto set-credentials) ;;
    esac
fi
echo
echo "Done. fortiauto now runs in the background."
echo "Change your saved login:"
echo "  cd \"$APP\" && $PY -m fortiauto set-credentials"
echo "Check on it any time:"
echo "  cd \"$APP\" && $PY -m fortiauto status"
