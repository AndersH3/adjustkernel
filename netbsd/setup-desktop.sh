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

fix_gnome40_keybindings_schema()
{
    schema_dir=/usr/pkg/share/glib-2.0/schemas
    schema="${schema_dir}/org.gnome.desktop.wm.keybindings.gschema.xml"
    backup="${schema}.pre-adjustkernel"

    # GNOME Shell/Mutter 40 still reads the toggle-shaded key.  Upstream
    # gsettings-desktop-schemas removed it in GNOME 45.  Current pkgsrc can
    # therefore combine an old gnome-shell/mutter with a much newer schemas
    # package, causing gnome-shell to abort at login with:
    #
    #   Settings schema 'org.gnome.desktop.wm.keybindings'
    #   does not contain a key named 'toggle-shaded'
    #
    # Only patch the compatibility key when it is actually absent.
    if /usr/pkg/bin/gsettings list-keys org.gnome.desktop.wm.keybindings 2>/dev/null |
        grep -qx 'toggle-shaded'; then
        return 0
    fi

    if [ ! -f "${schema}" ]; then
        echo "GNOME keybindings schema not found: ${schema}" >&2
        exit 1
    fi

    echo "Adding GNOME 40 compatibility key toggle-shaded to GSettings schema."

    if [ ! -f "${backup}" ]; then
        cp -p "${schema}" "${backup}"
    fi

    tmp="${schema}.tmp.$$"
    if ! awk '
        BEGIN { inserted = 0 }
        /<\/schema>/ && inserted == 0 {
            print "    <key name=\"toggle-shaded\" type=\"as\">"
            print "      <default>[]</default>"
            print "      <summary>Toggle shaded state</summary>"
            print "    </key>"
            inserted = 1
        }
        { print }
        END { if (inserted == 0) exit 1 }
    ' "${schema}" > "${tmp}"; then
        rm -f "${tmp}"
        echo "Could not patch ${schema}." >&2
        exit 1
    fi

    mv "${tmp}" "${schema}"

    if ! /usr/pkg/bin/glib-compile-schemas "${schema_dir}"; then
        echo "Schema compilation failed; restoring original file." >&2
        cp -p "${backup}" "${schema}"
        /usr/pkg/bin/glib-compile-schemas "${schema_dir}" || true
        exit 1
    fi

    if ! /usr/pkg/bin/gsettings list-keys org.gnome.desktop.wm.keybindings |
        grep -qx 'toggle-shaded'; then
        echo "toggle-shaded is still missing after schema compilation." >&2
        exit 1
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

# Apply the schema compatibility fix before starting/restarting the desktop.
fix_gnome40_keybindings_schema

# Install the GNOME Shell resource overlay.  GLib's G_RESOURCE_OVERLAYS lets
# us replace selected embedded JavaScript resources without rebuilding the
# binary gnome-shell package.
OVERLAY_SRC="${SCRIPT_DIR}/gnome-shell-overlay"
OVERLAY_DST="/usr/pkg/share/adjustkernel/gnome-shell-overlay"
if [ ! -f "${OVERLAY_SRC}/misc/parentalControlsManager.js" ]; then
    echo "GNOME Shell compatibility overlay is missing from the repository." >&2
    exit 1
fi
install -d -m 755 "${OVERLAY_DST}" "${OVERLAY_DST}/misc"
install -c -m 644     "${OVERLAY_SRC}/misc/parentalControlsManager.js"     "${OVERLAY_DST}/misc/parentalControlsManager.js"

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
echo "GNOME Shell compatibility overlay installed in ${OVERLAY_DST}."
echo "The session will be launched through ConsoleKit (ck-launch-session)."
echo "Restart XDM or reboot, then log in as ${USER_NAME}."
