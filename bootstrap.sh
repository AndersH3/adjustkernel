#!/bin/sh
# Bootstrap a fresh NetBSD system with pkgin and the packages used by this
# project. Run as root.
#
# Download directly from GitHub with NetBSD ftp(1):
#   ftp -4 -o bootstrap.sh \
#     https://raw.githubusercontent.com/AndersH3/adjustkernel/main/bootstrap.sh
#
# Then run:
#   sh bootstrap.sh

set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "bootstrap.sh must be run as root." >&2
    exit 1
fi

PATH="/usr/pkg/sbin:/usr/pkg/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

ARCH="$(uname -p)"
RELEASE="$(uname -r | cut -d_ -f1)"
PKG_PATH="https://cdn.NetBSD.org/pub/pkgsrc/packages/NetBSD/${ARCH}/${RELEASE}/All"
export PKG_PATH

echo "Using package repository:"
echo "  ${PKG_PATH}"

if ! command -v pkgin >/dev/null 2>&1; then
    pkg_add -v pkgin
fi

mkdir -p /usr/pkg/etc/pkgin
printf '%s\n' "${PKG_PATH}" > /usr/pkg/etc/pkgin/repositories.conf

pkgin -y update

# Basic tools.
pkgin -y install mc git

# Core GNOME/X11 stack.
#
# MesaLib is intentionally explicit.  NetBSD PR pkg/58858 documents a mutter
# packaging issue where MesaLib can be missing even though mutter needs it at
# runtime; the symptom can be black/unrendered windows or a failed GNOME
# session.  glx-utils provides glxinfo/glxgears for verification.
#
# ConsoleKit is explicit because GNOME on NetBSD uses it to identify the
# graphical login session/seat in place of systemd-logind.
pkgin -y install \
    MesaLib \
    glx-utils \
    consolekit \
    gnome-shell \
    gnome-session \
    gnome-settings-daemon \
    gnome-terminal \
    gnome-backgrounds \
    nautilus \
    eog \
    evince \
    gnome-calculator
