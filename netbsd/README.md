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

The bootstrap script installs `pkgin`, basic tools, ConsoleKit, and the GNOME
components available in the NetBSD binary package repository.

## Configure GNOME for XDM

If the repository is cloned locally:

```sh
sh netbsd/setup-desktop.sh anonymous
```

If the repository is not cloned, download and run the repository-maintained
installer directly:

```sh
ftp -4 -o install-from-github.sh \
  https://raw.githubusercontent.com/AndersH3/adjustkernel/main/netbsd/install-from-github.sh
sh install-from-github.sh anonymous
```

The setup script:

- enables the system D-Bus daemon;
- enables XDM;
- verifies that ConsoleKit's `ck-launch-session` is installed;
- installs `netbsd/xsession` as the user's `~/.xsession`;
- configures the X11 keyboard as Swedish;
- starts D-Bus immediately when needed.

GNOME on NetBSD runs under Xorg.  The session file launches GNOME as:

```sh
exec ck-launch-session gnome-session
```

This registers the graphical session with ConsoleKit.  Without that wrapper,
`gnome-session` can emit `GetSessionForUnixProcess failed` and the GNOME
Shell session may fall back to the "Oh no! Something has gone wrong" screen.

## Configuration fragments

- `rc.conf.desktop`: desktop-related `/etc/rc.conf` assignments.
- `wscons.conf.keyboard`: Swedish wscons console keyboard setting.
- `dhcpcd.conf.ipv4only`: optional IPv4-only dhcpcd setting.

These fragments are reference/configuration sources. Merge their settings into
the corresponding files under `/etc`; do not blindly overwrite an existing
system configuration.
