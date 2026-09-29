#!/bin/sh
# Collect GNOME/Xorg diagnostics on NetBSD.
# Usage: sh diagnose-gnome.sh [username]
# Default username: anonymous

set -u
USER_NAME="${1:-anonymous}"
HOME_DIR=$(getent passwd "${USER_NAME}" 2>/dev/null | awk -F: '{print $6}')

echo "=== SYSTEM ==="
uname -a
echo

echo "=== RELEVANT PACKAGES ==="
pkg_info 2>/dev/null | grep -E '^(MesaLib|glx-utils|consolekit|dbus|mutter|gnome-shell|gnome-session|gnome-settings-daemon)' || true
echo

echo "=== DBUS ==="
service dbus status 2>&1 || true
echo

echo "=== CONSOLEKIT ==="
if command -v ck-list-sessions >/dev/null 2>&1; then
    ck-list-sessions 2>&1 || true
else
    echo "ck-list-sessions not found"
fi
echo

echo "=== XSESSION ==="
if [ -n "${HOME_DIR}" ] && [ -f "${HOME_DIR}/.xsession" ]; then
    cat "${HOME_DIR}/.xsession"
else
    echo "No .xsession found for ${USER_NAME}"
fi
echo

echo "=== XSESSION ERRORS ==="
if [ -n "${HOME_DIR}" ] && [ -f "${HOME_DIR}/.xsession-errors" ]; then
    grep -Ei 'GetSessionForUnixProcess|consolekit|gnome-shell|mutter|fatal|critical|error|failed|segfault|GL|EGL|clutter|renderer'         "${HOME_DIR}/.xsession-errors" | tail -200
else
    echo "No .xsession-errors found for ${USER_NAME}"
fi
echo

echo "=== XORG ERRORS ==="
for f in /var/log/Xorg.0.log "${HOME_DIR}/.local/share/xorg/Xorg.0.log"; do
    if [ -f "${f}" ]; then
        echo "--- ${f} ---"
        grep -Ei '\(EE\)|error|failed|fatal|radeon|glamor|dri|glx|egl|opengl|llvmpipe' "${f}" | tail -200
    fi
done
