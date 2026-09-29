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

The bootstrap script installs `pkgin`, basic tools, ConsoleKit, MesaLib,
`glx-utils`, and the GNOME components available in the NetBSD binary package
repository.

MesaLib is installed explicitly because NetBSD PR pkg/58858 documents a mutter
packaging problem in which MesaLib may be absent even though mutter needs it at
runtime.  Typical symptoms include black/unrendered windows or a GNOME session
that fails during startup.

## Configure GNOME for XDM

If the repository is cloned locally:

```sh
sh netbsd/setup-desktop.sh anonymous
```

If the repository is not cloned:

```sh
ftp -4 -o install-from-github.sh \
  https://raw.githubusercontent.com/AndersH3/adjustkernel/main/netbsd/install-from-github.sh
sh install-from-github.sh anonymous
```

The setup script enables system D-Bus and XDM, verifies ConsoleKit, installs
`netbsd/xsession` as the user's `~/.xsession`, and configures the X11
keyboard as Swedish.

GNOME on NetBSD runs under Xorg.  The session currently launches through:

```sh
exec ck-launch-session gnome-session
```

## Diagnostics

To collect the relevant GNOME, ConsoleKit and Xorg failures:

```sh
ftp -4 -o diagnose-gnome.sh \
  https://raw.githubusercontent.com/AndersH3/adjustkernel/main/netbsd/diagnose-gnome.sh
sh diagnose-gnome.sh anonymous
```

For OpenGL verification from a running X session:

```sh
glxinfo -B
```

The renderer should identify working direct rendering rather than showing a
missing GL implementation.

## Configuration fragments

- `rc.conf.desktop`: desktop-related `/etc/rc.conf` assignments.
- `wscons.conf.keyboard`: Swedish wscons console keyboard setting.
- `dhcpcd.conf.ipv4only`: optional IPv4-only dhcpcd setting.

These fragments are reference/configuration sources. Merge their settings into
the corresponding files under `/etc`; do not blindly overwrite an existing
system configuration.
