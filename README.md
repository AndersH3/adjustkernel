# adjustkernel-ng (Python)

A conservative, heavily refactored Python successor to the historical NetBSD
`adjustkernel` script.  Its purpose is to derive a machine-specific kernel
configuration from the hardware that is actually attached at runtime, without
pretending that `dmesg` is a complete representation of NetBSD `config(5)`.

The historical pkgsrc `sysutils/adjustkernel` was removed in 2010 as broken.
This implementation is new code and is intentionally designed around current
NetBSD interfaces rather than transliterating the old Perl program.

## Design priorities

1. **Prefer `drvctl -t -l` over parsing `dmesg`.**  `drvctl(8)` exposes the live
   device tree directly.  `dmesg` is retained as a fallback and for offline
   analysis.
2. **Treat interface attributes conservatively.**  NetBSD documents that a
   runtime relation such as `audio0 at azalia0` can correspond to a kernel
   configuration rule such as `audio* at audiobus?`.  A naive textual parent
   comparison is therefore unsafe.
3. **Modify only active `instance at attachment ...` rules.**  Options,
   pseudo-devices, file systems, `makeoptions`, comments, and unrecognized or
   multi-line syntax are left untouched.
4. **Use NetBSD's own `config(1)` as the authority.**  Validation is enabled by
   default when `config(1)` and the kernel source tree can be found.
5. **Fail closed.**  Ambiguous topology or syntax causes an error or a keep,
   never a speculative removal.
6. **Support delta/overlay configs.**  `--style overlay` generates an
   `include "..."` plus safe `no ...` statements, matching the maintenance
   style recommended by `config.samples(5)`.

Primary NetBSD references:

- https://man.netbsd.org/drvctl.8
- https://man.netbsd.org/config.1
- https://man.netbsd.org/config.5
- https://man.netbsd.org/config.samples.5

## Libraries used deliberately

This project uses existing libraries where they remove boilerplate or encode a
well-understood abstraction:

| Library | Role |
|---|---|
| `typer` | typed command-line interface and help |
| `rich` | readable diagnostics and decision tables |
| `attrs` | small immutable data models |
| `cattrs` | structured JSON report conversion |
| `pyparsing` | conservative recognizer for editable config statements |
| `networkx` | device-tree graph representation and graph sanity checks |
| `more-itertools` | stable de-duplication in overlay generation |
| `platformdirs` | portable location for optional user settings |
| `filelock` | serialize concurrent output/in-place writers |
| `tomlkit` | parse optional TOML settings without inventing a config parser |
| `pytest` | regression tests (development dependency) |
| `hypothesis` | property-based testing support (development dependency) |
| `ruff` / `mypy` | linting and type checking (development dependencies) |

The runtime stack is intentionally mostly pure Python, which is useful on
NetBSD because it avoids unnecessary native-extension build dependencies.

## Installation

From the unpacked source directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install .
```

For development tools as well:

```sh
python3 -m pip install '.[dev]'
pytest
```

The installed commands are both `adjustkernel` and `adjustkernel-ng`.

## Typical use

Generate a commented copy of `GENERIC`:

```sh
cd /usr/src/sys/arch/amd64/conf
adjustkernel GENERIC -o MYKERNEL
```

Show every decision and a unified diff:

```sh
adjustkernel GENERIC -o MYKERNEL --show-decisions --diff
```

Generate the more maintainable overlay form:

```sh
adjustkernel GENERIC \
    --style overlay \
    --srcdir /usr/src/sys \
    -o MYKERNEL
```

This produces roughly:

```text
include "arch/amd64/conf/GENERIC"

no re* at pci?
no foo* at usb?
...
```

`config(5)` says that `no instance at attachment` ignores locator differences.
The renderer detects groups where that would remove a retained locator variant
and suppresses the unsafe negation instead.

## Inventory sources

Default mode is:

```text
--source auto
```

The acquisition order is:

1. `drvctl -t -l`
2. `/var/run/dmesg.boot`, if present
3. live `dmesg`

To force an offline boot log:

```sh
adjustkernel GENERIC \
    --source dmesg \
    --dmesg-file ./dmesg.boot \
    --no-validate
```

`drvctl` is preferred because its documented `-l` operation lists device-tree
children and `-t` prints the tree.  `dmesg` is human-oriented text and cannot
faithfully reveal interface-attribute names.

## Safety controls

### `--keep BASE`

Always retain a driver base even if it is not currently attached:

```sh
adjustkernel GENERIC --keep umass --keep cd -o MYKERNEL
```

This is useful for removable hardware you intentionally want supported.

### Protected devices

`mainbus` is protected by default.  Persistent defaults can be changed in the
TOML settings file.

### Validation

Validation defaults to on:

```sh
adjustkernel GENERIC --srcdir /usr/src/sys -o MYKERNEL
```

Internally the program writes the candidate to a temporary directory and runs
approximately:

```sh
config -s /usr/src/sys -b /tmp/.../build /tmp/.../MYKERNEL
```

If `config(1)` rejects the candidate, no output file is written.  `--force`
exists for expert review cases, but is intentionally explicit.

If `config(1)` is not installed, the program warns and continues because a
cross-build host may not have the native utility in `PATH`.  Use
`--config-tool /path/to/config` when appropriate.

### In-place editing

```sh
adjustkernel GENERIC --in-place
```

This first copies `GENERIC` to `GENERIC.bak`, then replaces the original with an
atomic same-filesystem rename while holding a file lock.

Overlay mode is deliberately forbidden with `--in-place`; otherwise the output
could include itself recursively.

## Optional settings

The default settings location is obtained with `platformdirs`; on a normal Unix
setup this is under the user's configuration directory.  An explicit file may
be supplied with `--settings-file`.

Example:

```toml
[adjustkernel]
source = "auto"
style = "comment"
keep = ["umass", "cd", "sd"]
protected = ["mainbus"]
```

Command-line `--keep` values are added to configured keeps.  An explicit
`--protected` list replaces the configured protected list for that run.

## JSON audit report

```sh
adjustkernel GENERIC \
    -o MYKERNEL \
    --json-report MYKERNEL.adjustkernel.json
```

The report records the inventory source, edge count, recognized rule count,
each keep/disable decision with its reason, and validation result.

## Why not parse all of `config(5)` in Python?

That would be a second, incomplete implementation of NetBSD's kernel
configuration language.  `config(5)` includes source-description statements,
interface attributes, dependencies, locators, conditionals, includes, prefixes,
and selection statements.  The safer architecture is:

- Python recognizes only the statement class it may edit;
- everything else remains byte-for-byte opaque;
- ambiguous cases are retained;
- NetBSD `config(1)` validates the result.

One explicit limitation follows from this policy: unusual multi-line attachment
statements are preserved rather than edited.  Ordinary NetBSD `GENERIC` device
attachment lines are normally one physical line, so this is a conservative
trade-off rather than a practical loss for typical use.

## Tests

The included tests cover:

- `drvctl -t -l` hierarchy parsing;
- timestamped `dmesg` parsing;
- wildcard and concrete instance matching;
- interface-attribute retention (`audio* at audiobus?`);
- absent driver removal;
- alternate concrete-parent removal;
- comment-mode rendering;
- overlay generation; and
- rejection of runtime graphs with multiple parents.

Run:

```sh
PYTHONPATH=src pytest -q
```

The source package supplied here passes all included tests in the development
environment.  A final integration run should still be performed on NetBSD so
that the local `drvctl(8)` output and `config(1)` are exercised directly.
