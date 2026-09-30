#!/usr/pkg/bin/python3.14
"""
Repair Swedish keyboard configuration on NetBSD and write a diagnostic report.

Run as root:

    python3.14 fix_keyboard.py

The script defaults to user "anonymous" and:
  * applies the Swedish wscons keyboard map immediately;
  * makes "encoding sv" persistent in /etc/wscons.conf;
  * makes wscons=YES persistent in /etc/rc.conf;
  * persists GNOME's XKB input source as Swedish;
  * ensures ~/.xsession reapplies the Swedish X11 layout at login;
  * writes ~/keyboard_fix_report.txt with before/after diagnostics.

It is deliberately idempotent and keeps one backup of each edited system file.
"""

from __future__ import annotations

import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

USER_NAME = "anonymous"
REPORT_NAME = "keyboard_fix_report.txt"

WSCONS_CONF = Path("/etc/wscons.conf")
RC_CONF = Path("/etc/rc.conf")
WSCONSCTL = Path("/sbin/wsconsctl")
SETXKBMAP = Path("/usr/X11R7/bin/setxkbmap")
GSETTINGS = Path("/usr/pkg/bin/gsettings")
DBUS_RUN_SESSION = Path("/usr/pkg/bin/dbus-run-session")


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
            timeout=30,
        )
        return p.returncode, p.stdout
    except Exception as exc:
        return 125, f"{type(exc).__name__}: {exc}\n"


def backup_once(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(path.name + ".adjustkernel.bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def replace_or_append_line(path: Path, predicate, replacement: str) -> None:
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(errors="replace").splitlines()

    changed = False
    out: list[str] = []
    for line in lines:
        if predicate(line) and not changed:
            out.append(replacement)
            changed = True
        elif predicate(line):
            # Drop duplicate active settings.
            continue
        else:
            out.append(line)

    if not changed:
        if out and out[-1] != "":
            out.append("")
        out.append(replacement)

    path.write_text("\n".join(out) + "\n")


def ensure_wscons() -> list[str]:
    log: list[str] = []

    backup_once(WSCONS_CONF)
    backup_once(RC_CONF)

    replace_or_append_line(
        WSCONS_CONF,
        lambda s: s.strip().startswith("encoding ") and not s.lstrip().startswith("#"),
        "encoding sv",
    )
    log.append("Set /etc/wscons.conf: encoding sv")

    replace_or_append_line(
        RC_CONF,
        lambda s: s.strip().startswith("wscons=") and not s.lstrip().startswith("#"),
        "wscons=YES",
    )
    log.append("Set /etc/rc.conf: wscons=YES")

    if WSCONSCTL.exists():
        rc, out = run([str(WSCONSCTL), "-k", "-w", "encoding=sv"])
        if rc != 0:
            rc2, out2 = run([str(WSCONSCTL), "-w", "encoding=sv"])
            log.append(
                f"wsconsctl -k result: exit={rc}\n{out.strip()}\n"
                f"wsconsctl fallback result: exit={rc2}\n{out2.strip()}"
            )
        else:
            log.append(f"Applied console map immediately: exit={rc}\n{out.strip()}")
    else:
        log.append("/sbin/wsconsctl not found")

    return log


def marker_block() -> str:
    return """# BEGIN adjustkernel Swedish keyboard
if [ -x /usr/X11R7/bin/setxkbmap ]; then
    /usr/X11R7/bin/setxkbmap se
fi
# END adjustkernel Swedish keyboard
"""


def ensure_xsession(home: Path) -> str:
    path = home / ".xsession"
    if not path.exists():
        return f"{path} does not exist; GNOME X11 startup file was not changed."

    text = path.read_text(errors="replace")
    begin = "# BEGIN adjustkernel Swedish keyboard"
    end = "# END adjustkernel Swedish keyboard"

    # Remove a previous managed block.
    if begin in text and end in text:
        before, rest = text.split(begin, 1)
        _, after = rest.split(end, 1)
        text = before.rstrip() + "\n" + after.lstrip("\n")

    # Remove a simple legacy "setxkbmap se" line to avoid duplicate calls.
    cleaned: list[str] = []
    for line in text.splitlines():
        if line.strip() in {"setxkbmap se", "/usr/X11R7/bin/setxkbmap se"}:
            continue
        cleaned.append(line)
    text = "\n".join(cleaned) + "\n"

    block = marker_block()
    exec_line = "exec ck-launch-session gnome-session"
    if exec_line in text:
        text = text.replace(exec_line, block + "\n" + exec_line, 1)
    else:
        text += "\n" + block

    path.write_text(text)
    os.chown(path, pwd.getpwnam(USER_NAME).pw_uid, pwd.getpwnam(USER_NAME).pw_gid)
    return f"Updated {path} to run setxkbmap se at X11 login."


def set_gnome_input_source(pw: pwd.struct_passwd) -> list[str]:
    log: list[str] = []

    if not GSETTINGS.exists():
        return ["/usr/pkg/bin/gsettings not found; GNOME input source not changed."]

    base_env = {
        "HOME": pw.pw_dir,
        "USER": pw.pw_name,
        "LOGNAME": pw.pw_name,
        "SHELL": pw.pw_shell or "/bin/sh",
        "PATH": "/usr/pkg/bin:/usr/pkg/sbin:/usr/X11R7/bin:/usr/bin:/bin:/sbin:/usr/sbin",
    }

    commands = [
        [
            str(GSETTINGS),
            "set",
            "org.gnome.desktop.input-sources",
            "sources",
            "[('xkb', 'se')]",
        ],
        [
            str(GSETTINGS),
            "set",
            "org.gnome.desktop.input-sources",
            "xkb-options",
            "[]",
        ],
    ]

    for command in commands:
        if DBUS_RUN_SESSION.exists():
            full = [
                "/usr/bin/su",
                "-m",
                pw.pw_name,
                "-c",
                " ".join("'" + x.replace("'", "'\\''") + "'" for x in [str(DBUS_RUN_SESSION), "--", *command]),
            ]
            rc, out = run(full, env=base_env)
        else:
            full = [
                "/usr/bin/su",
                "-m",
                pw.pw_name,
                "-c",
                " ".join("'" + x.replace("'", "'\\''") + "'" for x in command),
            ]
            rc, out = run(full, env=base_env)
        log.append(f"{' '.join(command)}\nexit={rc}\n{out.strip()}")

    return log


def collect_report(pw: pwd.struct_passwd, actions: list[str]) -> Path:
    report = Path(pw.pw_dir) / REPORT_NAME
    sections: list[str] = []

    sections.append("ACTIONS\n=======\n" + "\n\n".join(actions))

    if WSCONS_CONF.exists():
        lines = [
            line for line in WSCONS_CONF.read_text(errors="replace").splitlines()
            if "encoding" in line or line.strip().startswith("keyboard")
        ]
        sections.append("WSCONS.CONF\n===========\n" + "\n".join(lines))

    if RC_CONF.exists():
        lines = [
            line for line in RC_CONF.read_text(errors="replace").splitlines()
            if line.strip().startswith("wscons=")
        ]
        sections.append("RC.CONF\n=======\n" + "\n".join(lines))

    if WSCONSCTL.exists():
        rc, out = run([str(WSCONSCTL), "-k", "encoding"])
        if rc != 0:
            rc, out = run([str(WSCONSCTL), "encoding"])
        live = out.strip()
        note = ""
        # On NetBSD, KB_FI and KB_SV intentionally share encoding value
        # 0x0900. wsconsctl prints the first symbolic name for that value,
        # which is "fi", even when "encoding sv" was successfully requested.
        # The Swedish and Finnish PC layouts are therefore reported through
        # the same wscons encoding value; X11 still uses the explicit "se"
        # layout configured separately below.
        if live in {"encoding=fi", "encoding -> fi"}:
            note = (
                "\nNOTE: NetBSD aliases KB_SV and KB_FI to the same wscons "
                "encoding value (0x0900), so a successful Swedish setting may "
                "be displayed as 'fi'."
            )
        sections.append(
            f"LIVE WSCONS\n===========\nexit={rc}\n{live}{note}"
        )

    if GSETTINGS.exists():
        env = {
            "HOME": pw.pw_dir,
            "USER": pw.pw_name,
            "LOGNAME": pw.pw_name,
            "PATH": "/usr/pkg/bin:/usr/bin:/bin",
        }
        command = [
            "/usr/bin/su",
            "-m",
            pw.pw_name,
            "-c",
            f"{GSETTINGS} get org.gnome.desktop.input-sources sources",
        ]
        rc, out = run(command, env=env)
        sections.append(f"GNOME INPUT SOURCES\n===================\nexit={rc}\n{out.strip()}")

    xsession = Path(pw.pw_dir) / ".xsession"
    if xsession.exists():
        selected = [
            line for line in xsession.read_text(errors="replace").splitlines()
            if "setxkbmap" in line or "adjustkernel Swedish keyboard" in line
        ]
        sections.append("XSESSION KEYBOARD LINES\n=======================\n" + "\n".join(selected))

    report.write_text("\n\n".join(sections) + "\n")
    os.chown(report, pw.pw_uid, pw.pw_gid)
    return report


def main() -> int:
    if os.geteuid() != 0:
        print("Run this script as root (use su first).", file=sys.stderr)
        return 1

    try:
        pw = pwd.getpwnam(USER_NAME)
    except KeyError:
        print(f"User {USER_NAME!r} does not exist.", file=sys.stderr)
        return 2

    actions: list[str] = []
    actions.extend(ensure_wscons())
    actions.append(ensure_xsession(Path(pw.pw_dir)))
    actions.extend(set_gnome_input_source(pw))

    report = collect_report(pw, actions)
    print(f"Keyboard repair completed.")
    print(f"Report: {report}")
    print("Log out of XDM/GNOME and log in again, or reboot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
