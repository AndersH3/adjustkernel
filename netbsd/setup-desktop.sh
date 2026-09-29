#!/bin/sh
# Configure an installed pkgsrc GNOME desktop for XDM on NetBSD.
# Usage: sh netbsd/setup-desktop.sh [username]
# Default username: anonymous

set -eu

USER_NAME="${1:-anonymous}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ "$(id -u)" -ne 0 ]; then
    echo "setup-desktop.sh must be run as root." >&2
    exit 1
fi

if [ "$(uname -s)" != "NetBSD" ]; then
    echo "This script is intended for NetBSD." >&2
    exit 1
fi

if ! id "${USER_NAME}" >/dev/null 2>&1; then
    echo "No such user: ${USER_NAME}" >&2
    exit 1
fi

if [ ! -x /usr/pkg/bin/ck-launch-session ]; then
    echo "ConsoleKit is required; install it with: pkgin install consolekit" >&2
    exit 1
fi

set_rc_var()
{
    key=$1
    value=$2

    if grep -q "^[[:space:]]*${key}=" /etc/rc.conf; then
        sed "s|^[[:space:]]*${key}=.*|${key}=${value}|" /etc/rc.conf > /etc/rc.conf.new
        mv /etc/rc.conf.new /etc/rc.conf
    else
        printf '%s=%s\n' "${key}" "${value}" >> /etc/rc.conf
    fi
}

# GNOME requires a system-wide D-Bus daemon.
if [ ! -x /etc/rc.d/dbus ]; then
    if [ ! -f /usr/pkg/share/examples/rc.d/dbus ]; then
        echo "D-Bus rc.d example not found; install the dbus package first." >&2
        exit 1
    fi
    cp /usr/pkg/share/examples/rc.d/dbus /etc/rc.d/dbus
    chmod 755 /etc/rc.d/dbus
fi

set_rc_var dbus YES
set_rc_var xdm YES

HOME_DIR=$(getent passwd "${USER_NAME}" | awk -F: '{print $6}')
if [ -z "${HOME_DIR}" ] || [ ! -d "${HOME_DIR}" ]; then
    echo "Cannot determine home directory for ${USER_NAME}." >&2
    exit 1
fi

install -c -m 755 "${SCRIPT_DIR}/xsession" "${HOME_DIR}/.xsession"
chown "${USER_NAME}" "${HOME_DIR}/.xsession"

if ! service dbus status >/dev/null 2>&1; then
    service dbus start
fi

echo "GNOME/XDM setup complete for ${USER_NAME}."
echo "The session will be launched through ConsoleKit (ck-launch-session)."
echo "Reboot, or restart XDM, then log in as ${USER_NAME}."
