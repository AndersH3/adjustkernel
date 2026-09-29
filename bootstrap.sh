#!/bin/sh
# Bootstrap a fresh NetBSD system with pkgin and the packages used by this
# project.  Run as root.
#
# Download directly from GitHub with NetBSD ftp(1):
#   ftp -o bootstrap.sh \
#     https://raw.githubusercontent.com/AndersH3/adjustkernel/main/bootstrap.sh
#
# Then run:
#   sh bootstrap.sh

set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "bootstrap.sh must be run as root." >&2
    exit 1
fi

# pkgsrc installs third-party programs under /usr/pkg.
PATH="/usr/pkg/sbin:/usr/pkg/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

# Strip only a NetBSD release suffix such as _STABLE or _GENERIC.
# This follows the PKG_PATH form recommended by the NetBSD Guide.
ARCH="$(uname -p)"
RELEASE="$(uname -r | cut -d_ -f1)"
PKG_PATH="https://cdn.NetBSD.org/pub/pkgsrc/packages/NetBSD/${ARCH}/${RELEASE}/All"
export PKG_PATH

echo "Using package repository:"
echo "  ${PKG_PATH}"

if ! command -v pkgin >/dev/null 2>&1; then
    pkg_add -v pkgin
fi

# Make pkgin use the same binary repository explicitly.
mkdir -p /usr/pkg/etc/pkgin
printf '%s\n' "${PKG_PATH}" > /usr/pkg/etc/pkgin/repositories.conf

pkgin -y update
pkgin -y install mc git gnome
