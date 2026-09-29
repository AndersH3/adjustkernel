# NetBSD setup files

These files keep the NetBSD bootstrap and desktop configuration under version
control instead of requiring one-off edits on the target machine.

## Bootstrap packages

From a fresh NetBSD installation, as root:

```sh
ftp -4 -o bootstrap.sh \
  https://raw.githubusercontent.com/AndersH3/adjustkernel/main/bootstrap.sh
sh bootstrap.sh
```

The bootstrap script installs `pkgin`, basic tools, and the GNOME components
available in the NetBSD binary package repository.

## Configure GNOME for XDM

When the repository is cloned locally:

```sh
sh netbsd/setup-desktop.sh anonymous
```

The setup script:

- enables the system D-Bus daemon;
- enables XDM;
- installs `netbsd/xsession` as the user's `~/.xsession`;
- configures the X11 keyboard as Swedish;
- starts D-Bus immediately when needed.

The NetBSD GNOME documentation requires the system-wide D-Bus daemon before
starting a GNOME session and uses `exec gnome-session` for the X11 session.

## Configuration fragments

- `rc.conf.desktop`: desktop-related `/etc/rc.conf` assignments.
- `wscons.conf.keyboard`: Swedish wscons console keyboard setting.
- `dhcpcd.conf.ipv4only`: optional IPv4-only dhcpcd setting.

These fragments are reference/configuration sources. Merge their settings into
the corresponding files under `/etc`; do not blindly overwrite an existing
system configuration.
