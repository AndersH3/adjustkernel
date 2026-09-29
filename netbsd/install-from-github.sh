#!/bin/sh
# Download the repository-maintained NetBSD desktop setup files and apply them.
# Usage: sh install-from-github.sh [username]
# Default username: anonymous

set -eu

USER_NAME="${1:-anonymous}"
BASE_URL="https://raw.githubusercontent.com/AndersH3/adjustkernel/main/netbsd"
WORKDIR="${TMPDIR:-/tmp}/adjustkernel-netbsd"

if [ "$(id -u)" -ne 0 ]; then
    echo "install-from-github.sh must be run as root." >&2
    exit 1
fi

mkdir -p "${WORKDIR}"

ftp -4 -o "${WORKDIR}/setup-desktop.sh" "${BASE_URL}/setup-desktop.sh"
ftp -4 -o "${WORKDIR}/xsession" "${BASE_URL}/xsession"

chmod 755 "${WORKDIR}/setup-desktop.sh" "${WORKDIR}/xsession"

sh "${WORKDIR}/setup-desktop.sh" "${USER_NAME}"
