#!/usr/pkg/bin/python3.14
"""Collect NetBSD GNOME/GJS diagnostics into one text file.

Run after a failed GNOME login, preferably as root:
    python3.14 netbsd_gnome_diag.py

Options:
    --user anonymous
    --output /tmp/netbsd-gnome-diagnosis.txt
    --skip-ktrace

The script is diagnostic only. It does not change PaX flags, packages,
X configuration, or sysctls. It creates only temporary ktrace files in /tmp.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT = 30


def run(cmd, *, env=None, timeout=TIMEOUT):
    try:
        p = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout
    except FileNotFoundError:
        return 127, f"{cmd[0]}: command not found\n"
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return 124, f"{out}\n[TIMEOUT after {timeout}s]\n"
    except Exception as e:
        return 125, f"[exception: {e}]\n"


def shell(command, *, env=None, timeout=TIMEOUT):
    return run(["/bin/sh", "-c", command], env=env, timeout=timeout)


def section(fp, title, text):
    fp.write("\n" + "=" * 78 + "\n")
    fp.write(title + "\n")
    fp.write("=" * 78 + "\n")
    fp.write(text)
    if not text.endswith("\n"):
        fp.write("\n")


def cmd_section(fp, title, cmd, *, env=None, timeout=TIMEOUT):
    rc, out = run(cmd, env=env, timeout=timeout)
    section(fp, title, "$ " + " ".join(cmd) + f"\n[exit={rc}]\n" + out)


def shell_section(fp, title, command, *, env=None, timeout=TIMEOUT):
    rc, out = shell(command, env=env, timeout=timeout)
    section(fp, title, f"$ {command}\n[exit={rc}]\n{out}")


def tail_text(path, n=500):
    try:
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(lines[-n:]) + "\n"
    except FileNotFoundError:
        return f"{path}: not found\n"
    except Exception as e:
        return f"{path}: {e}\n"


def filter_text(text, words):
    words = [w.lower() for w in words]
    rows = [line for line in text.splitlines()
            if any(w in line.lower() for w in words)]
    return ("\n".join(rows) + "\n") if rows else "[no matching lines]\n"


def which(*names):
    for name in names:
        p = shutil.which(name)
        if p:
            return p
    return None


def ktrace_gjs(fp, gjs, disable_jit):
    ktrace = which("ktrace")
    kdump = which("kdump")
    title = f"GJS KTRACE TEST: GJS_DISABLE_JIT={1 if disable_jit else 0}"
    if not ktrace or not kdump:
        section(fp, title, "ktrace or kdump not found; skipped.\n")
        return

    js = (
        "function f(x){return ((x*3+1)^0x55aa55aa)|0;}"
        "let s=0;"
        "for(let i=0;i<3000000;i++){s=(s+f(i))|0;}"
        "print(s);"
    )

    env = os.environ.copy()
    env.pop("GJS_DISABLE_JIT", None)
    if disable_jit:
        env["GJS_DISABLE_JIT"] = "1"

    fd, trace_path = tempfile.mkstemp(prefix="gjs-ktrace-", suffix=".out", dir="/tmp")
    os.close(fd)
    try:
        rc, gout = run([ktrace, "-f", trace_path, gjs, "-c", js], env=env, timeout=60)
        drc, dump = run([kdump, "-f", trace_path], timeout=60)
        interesting = filter_text(
            dump,
            [
                "mprotect", "mmap", "munmap", "prot_exec",
                "eacces", "eperm", "enomem", "einval",
                "sigsegv", "sigbus", "signal", "reprotect",
                "moz_crash", "errno",
            ],
        )
        section(
            fp,
            title,
            f"gjs exit={rc}\n{gout}\n"
            f"kdump exit={drc}\n"
            "--- filtered kdump ---\n" + interesting,
        )
    finally:
        try:
            os.unlink(trace_path)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="anonymous")
    ap.add_argument("--output", default="netbsd-gnome-diagnosis.txt")
    ap.add_argument("--skip-ktrace", action="store_true")
    args = ap.parse_args()

    try:
        pw = pwd.getpwnam(args.user)
    except KeyError:
        print(f"No such user: {args.user}", file=sys.stderr)
        return 2

    home = Path(pw.pw_dir)
    output = Path(args.output).expanduser().resolve()

    with output.open("w", encoding="utf-8") as fp:
        section(fp, "REPORT METADATA", "\n".join([
            f"generated={dt.datetime.now().astimezone().isoformat()}",
            f"python={sys.version.replace(chr(10), ' ')}",
            f"collector_uid={os.getuid()}",
            f"target_user={args.user}",
            f"target_uid={pw.pw_uid}",
            f"target_home={home}",
        ]) + "\n")

        cmd_section(fp, "SYSTEM", ["uname", "-a"])
        shell_section(fp, "CPU / MEMORY",
                      "sysctl hw.model hw.ncpu hw.physmem64 hw.usermem64 2>&1")

        shell_section(
            fp,
            "RELEVANT PACKAGES",
            r"pkg_info 2>/dev/null | egrep -i '^(gjs|mozjs|gnome-shell|gnome-session|mutter|MesaLib|glx-utils|consolekit|dbus|gtk|glib|cairo|libffi|llvm)' | sort",
        )

        for exe in ("/usr/pkg/bin/gnome-shell", "/usr/pkg/bin/gjs", "/usr/pkg/bin/gjs-console"):
            if Path(exe).exists():
                cmd_section(fp, f"PAX FLAGS: {exe}", ["paxctl", exe])
                cmd_section(fp, f"FILE: {exe}", ["file", exe])
                cmd_section(fp, f"LDD: {exe}", ["ldd", exe])

        shell_section(
            fp,
            "PAX / SECURITY SYSCTLS",
            r"sysctl -a 2>/dev/null | egrep -i '(^security\.pax|pax|mprotect|aslr|w\^x)'",
        )
        shell_section(fp, "RESOURCE LIMITS", "ulimit -a")
        shell_section(
            fp,
            "CORE-DUMP SETTINGS",
            r"sysctl -a 2>/dev/null | egrep -i '(core|coredump)'",
        )
        shell_section(
            fp,
            "RECENT CORE FILES",
            f"find /var/crash /tmp {home} -type f \\( -name '*.core' -o -name 'core' -o -name 'core.*' \\) -print -ls 2>/dev/null | tail -100",
        )

        cmd_section(fp, "DBUS STATUS", ["service", "dbus", "status"])
        if which("ck-list-sessions"):
            cmd_section(fp, "CONSOLEKIT SESSIONS", ["ck-list-sessions"])

        shell_section(
            fp,
            "TMP / X SOCKET DIRECTORY PERMISSIONS",
            "ls -ld /tmp /tmp/.ICE-unix /tmp/.X11-unix 2>&1",
        )

        xsession = home / ".xsession"
        section(fp, "XSESSION", tail_text(xsession, 100))

        xerr = home / ".xsession-errors"
        xerr_text = tail_text(xerr, 1200)
        section(fp, "XSESSION ERRORS", xerr_text)
        section(
            fp,
            "XSESSION ERRORS - CRITICAL FILTER",
            filter_text(
                xerr_text,
                [
                    "moz_crash", "reprotect", "executableallocator",
                    "signal 11", "sigsegv", "gnome-shell", "mutter",
                    "fatal", "critical", "failed", "error",
                    "consolekit", "getsession",
                ],
            ),
        )

        for log in (Path("/var/log/Xorg.0.log"), home / ".local/share/xorg/Xorg.0.log"):
            if log.exists():
                text = tail_text(log, 2000)
                section(fp, f"XORG LOG: {log}", text)
                section(
                    fp,
                    f"XORG FILTER: {log}",
                    filter_text(
                        text,
                        ["(ee)", "(ww)", "error", "failed", "i915", "radeon",
                         "dri", "glx", "egl", "aiglx", "glamor", "llvmpipe"],
                    ),
                )

        shell_section(
            fp,
            "DMESG FILTER",
            r"dmesg 2>&1 | egrep -i '(error|fail|fault|segv|trap|pax|mprotect|out of memory|oom|i915|radeon|drm|audio_drain|sdmmc|tpm)' | tail -500",
        )

        shell_section(
            fp,
            "VERSIONS",
            r'''for x in /usr/pkg/bin/gnome-shell /usr/pkg/bin/gjs /usr/pkg/bin/gjs-console; do
  [ -x "$x" ] || continue
  echo "### $x"
  "$x" --version 2>&1 || true
done''',
        )

        shell_section(fp, "MOUNTS", "mount")
        shell_section(
            fp,
            "PROCESS SNAPSHOT",
            r"ps axww -o pid,ppid,uid,stat,command 2>/dev/null | egrep -i '(Xorg|xdm|gnome|mutter|gjs|dbus|consolekit)'",
        )

        gjs = which("gjs") or "/usr/pkg/bin/gjs"
        if not args.skip_ktrace and Path(gjs).exists():
            ktrace_gjs(fp, gjs, False)
            ktrace_gjs(fp, gjs, True)
        else:
            section(fp, "GJS KTRACE TESTS", "Skipped.\n")

        section(
            fp,
            "HOW TO READ THE KTRACE RESULT",
            """Compare the two GJS ktrace tests.

If the JIT-enabled test crashes but GJS_DISABLE_JIT=1 succeeds, inspect the last
mmap/mprotect call and errno before the signal.

If both succeed, standalone GJS can allocate/reprotect executable memory and the
remaining failure is more specific to gnome-shell or its startup environment.

If both fail, compare the exact errno, PaX flags, and security sysctls before
changing any global security setting.
""",
        )

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
