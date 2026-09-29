PKG_PATH="https://cdn.NetBSD.org/pub/pkgsrc/packages/NetBSD/$(uname -p)/$(uname -r|cut -f '1 2' -d.)/All/"
export PKG_PATH
pkg_add pkgin
pkg_add mc
pkg_add git
pkg_add gnome
