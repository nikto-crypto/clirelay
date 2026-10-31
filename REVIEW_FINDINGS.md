# clirelay vs Click 8.5.0 — Independent Differential Review

Reviewer probe of `clirelay` (`src/clirelay/`) against the bytecode-only Click
8.5.0 oracle, used strictly as a black box through its public API. Every repro
below was run with `/Users/nicholasserapiglia/Projects/clirelay/.venv/bin/python`
(Python 3.15, matching the oracle) with both libraries importable in one
process. Comparison was done through each library's `CliRunner`, through direct
public calls (`get_help`, `HelpFormatter`, `to_info_dict`, `style`, …), and the
only normalization applied is the contract-permitted one (`clirelay.`→`click.`,
mask `0x<hex>`).

**13 confirmed mismatches** across parsing/resolution, help formatting,
prompting, error reporting, terminal helpers, decorators, and `to_info_dict`.
These are in areas the existing suite under-exercises (the suite always passes an
explicit `terminal_width`, rarely raises errors from inside callbacks, and masks
one `to_info_dict` field with an out-of-contract `.replace`).

Severity legend: **High** = wrong result/crash in ordinary use; **Medium** =
wrong output text / wrong error channel; **Low** = niche/testing-only.

---

## 1. `auto_envvar_prefix` never resolves a value  — High — channel: stdout/return value

Click reads option values from the auto-derived environment variable
(`PREFIX_NAME`); clirelay ignores it entirely (works only for the help display).

```python
def build(c):
    @c.command(context_settings={"auto_envvar_prefix": "APP"})
    @c.option("--name")
    def cli(name): c.echo(repr(name))
    return cli
# invoke with args=[] env={"APP_NAME": "fromenv"}
```
- **oracle**: output `'fromenv\n'`
- **clirelay**: output `'None\n'`

Root cause: `core.py` — `Parameter.resolve_envvar_value` (≈L506) only consults
`self.envvar`, and `Option` has **no** `resolve_envvar_value` override to consult
`ctx.auto_envvar_prefix`. (The prefix is computed correctly at `core.py` L169-176
and used for the help string at L833-836, but never for value resolution.)

---

## 2. `File(lazy=True)` read of a missing file crashes instead of a usage error  — High — channel: exit code / stderr / exception

With an explicit `lazy=True` on a read-mode `File`, Click validates existence at
parse time and reports a `UsageError`; clirelay lets a raw `FileNotFoundError`
escape.

```python
def build(c):
    @c.command()
    @c.argument("f", type=c.File(lazy=True))
    def cli(f): c.echo(f.name)
    return cli
# argv: ["nope.txt"]  (file does not exist)
```
- **oracle**: exit `2`,
  stderr `Error: Invalid value for 'F': 'nope.txt': No such file or directory`
- **clirelay**: exit `1`, uncaught `FileNotFoundError: [Errno 2] No such file or directory: 'nope.txt'`

Root cause: `_files.py` L32-34 — `LazyFile.__init__` does `open(filename,
mode).close()` to fail early, raising `FileNotFoundError`; `File.convert`
(`types.py` L544-550) builds the `LazyFile` **outside** its `try/except OSError`,
so the error is never converted to a `BadParameter`.

---

## 3. CliRunner fake streams have no `name` (`<stdin>`/`<stdout>`/`<stderr>`)  — Low — channel: return value / exception (under CliRunner)

Click's testing streams report `name == "<stdin>"` / `"<stdout>"`; clirelay's do
not (the class is literally named `_NamedTextIO` but never assigns a name, and
`sys.stdin` is a bare `TextIOWrapper`). Observable via `File('-')` + `.name`.

```python
def build(c):
    @c.command()
    @c.argument("f", type=c.File("w"))
    def cli(f): c.echo(f.name)
    return cli
# argv: ["-"]
```
- **oracle**: exit `0`, output `'<stdout>\n'`
- **clirelay**: exit `1`, `AttributeError: 'BytesIOCopy' object has no attribute 'name'`
  (read-mode `['-']` → `'_io.BytesIO' object has no attribute 'name'`)

Root cause: `testing.py` L88-92 (`_NamedTextIO` sets no `name`), L212
(`text_input = io.TextIOWrapper(...)` with no name), L214-218. Only manifests
under `CliRunner`; real stdio has `.name`.

---

## 4. `HelpFormatter` auto-width omits Click's `-2` reserve and 50-column floor  — Medium — channel: help text

When the width is auto-detected (i.e. `terminal_width` not supplied), Click
computes `width = max(min(detected, max_content_width or 80) - 2, 50)`. clirelay
uses `min(detected, max_width)` with **no** `-2` and **no** floor.

```python
from clirelay.formatting import HelpFormatter   # and click.formatting
HelpFormatter(max_width=None).width   # oracle 78 / clirelay 80
HelpFormatter(max_width=60).width     # oracle 58 / clirelay 60
HelpFormatter(max_width=40).width     # oracle 50 (floored) / clirelay 40
HelpFormatter(max_width=200).width    # oracle 78 / clirelay 80
```
Also reproducible end-to-end via a directly-built context:
```python
ctx = c.Context(cli, info_name="cli", max_content_width=40)
cli.get_help(ctx)   # oracle wraps the help column at 50, clirelay at 40
```
- Default (no settings) help wraps at **78** in Click, **80** in clirelay.

Root cause: `formatting.py` L85 `width = min(_detect_columns(), max_width)` — missing `max(... - 2, 50)`.

Note: this is **masked under `CliRunner`** in this environment (both render at
80), and the existing help tests always pass an explicit `terminal_width` (which
Click uses verbatim, no `-2`), so the suite never exercises the auto path. It is
real for any code path that builds a `Context`/`HelpFormatter` directly or runs
the program against an actual terminal of width > 52.

---

## 5. `UsageError`/`BadParameter`/`MissingParameter`/`BadArgumentUsage` raised inside a callback lose the “Try … --help” hint  — Medium — channel: stderr

When one of these is raised from user code **without** an explicit `ctx`, Click
still prints the `Try 'cli --help' for help.` line; clirelay omits it.

```python
def build(c):
    @c.command()
    @c.argument("x")
    def cli(x): raise c.BadArgumentUsage("bad arg here")
    return cli
# argv: ["v"]
```
- **oracle**: `Usage: cli [OPTIONS] X\nTry 'cli --help' for help.\n\nError: bad arg here\n`
- **clirelay**: `Usage: cli [OPTIONS] X\n\nError: bad arg here\n`

Same divergence for `raise c.UsageError(...)`, `raise c.BadParameter(...,
param_hint=...)`, and `raise c.MissingParameter(...)` from a callback.
`ctx.fail("...")` is **correct** (it passes `ctx` at construction), which pins
the cause.

Root cause: `exceptions.py` L52 freezes `self.cmd = self.ctx.command if self.ctx
else None` at construction. When the exception is raised with `ctx=None` and
`ctx` is attached later by `augment_usage_errors` (`core.py` L67-69 sets only
`e.ctx`, not `e.cmd`), `show()` (L61) sees `self.cmd is None` and suppresses the
hint. Fix: recompute `cmd` from `self.ctx` in `show()`, or update `e.cmd` in
`augment_usage_errors`.

---

## 6. `progressbar` produces no output on a non-terminal  — Medium — channel: stdout

Click's progress bar, when the target is not a TTY, still emits the label line
(once) plus a trailing newline. clirelay emits nothing.

```python
import io
buf = io.StringIO()
with c.progressbar([1,2,3], label="work", file=buf) as bar:
    for _ in bar: pass
buf.getvalue()
```
- **oracle**: `'work\n'`  (no label → `'\n'`)
- **clirelay**: `''`

Root cause: `_term.py` L309-314 — `ProgressBar.render_progress` and
`render_finish` are `return None` stubs (“verified separately”), so **all**
non-interactive output is absent, not just the timing-dependent bar.

---

## 7. Option prompt ignores the option's `show_default`  — Medium — channel: stdout (prompt text)

`show_default=False` should hide the default in the prompt; a string
`show_default` should be shown in parentheses. clirelay always shows the raw
default.

```python
def build(c):
    @c.command()
    @c.option("--x", prompt=True, default="d", show_default=False)
    def cli(x): c.echo(x)
    return cli
# input "\n"
```
- **oracle**: prompt `X: `       (string case `show_default="custom"` → `X [(custom)]: `)
- **clirelay**: prompt `X [d]: `  (string case also `X [d]: `)

Root cause: `core.py` `Option.prompt_for_value` (≈L759-771) calls `_prompt_fn`
without forwarding `self.show_default`, so `termui.prompt`'s default
`show_default=True` always applies.

---

## 8. Shared-destination flag default resolves to `True` instead of its `flag_value`  — High — channel: stdout/return value

Two options writing one destination via `flag_value`, one marked `default=True`:
Click resolves the unset value to that option's `flag_value`; clirelay returns
the raw boolean `True`.

```python
def build(c):
    @c.option("--upper", "transform", flag_value="upper")
    @c.option("--lower", "transform", flag_value="lower", default=True)
    @c.command()
    def cli(transform): c.echo(transform)
    return cli
# argv: []  (no flag given)
```
- **oracle**: `'lower\n'`
- **clirelay**: `'True\n'`

(`--upper` explicitly given works in both.) Root cause: `core.py`
`Option.get_default` (L784-791) returns the raw default (`True`) for a flag with
no secondary opts, instead of mapping a truthy default to `self.flag_value`.

---

## 9. `prompt_required=False` is unimplemented  — High — channel: exit code / stdout / stderr

The option is accepted but the semantics (“only prompt if the flag is given with
no value; otherwise fall back to default”) are ignored.

```python
def build(c):
    @c.command()
    @c.option("--name", prompt=True, prompt_required=False, default="d")
    def cli(name): c.echo(name)
    return cli
```
- argv `[]`:       oracle exit `0` output `'d\n'`;  clirelay exit `1` output `'Aborted!\nName [d]: '` (it prompts and aborts on EOF)
- argv `['--name']` (input `typed\n`): oracle prompts → `'Name [d]: typed\ntyped\n'`; clirelay exit `2` `Error: Option '--name' requires an argument.`

Root cause: `prompt_required` is stored (`core.py` L624) but never consulted;
`Option.consume_value` (L741-757) prompts whenever the value is `None` and a
prompt is configured, and the parser still treats `--name` as value-requiring.

---

## 10. `_make_default_short_help` does not reserve space for its ellipsis  — Medium — channel: help text / completion help

When a command's first help line is truncated for the command list, Click sizes
the result so that the appended `...` fits within the limit; clirelay truncates
the text to the full limit and then appends `...`, overshooting by ~3+ chars.

```python
HELP = "This is a very long first line of help text that should get truncated with an ellipsis."
@c.command(help=HELP)
def cli(): pass
cli.get_short_help_str(45)
```
- **oracle**: `'This is a very long first line of help...'`  (len 41)
- **clirelay**: `'This is a very long first line of help text...'` (len 46)

Reproduces in a normal group listing (`group --help` at widths 40 and 80 differ;
60 happens to coincide) and anywhere `get_short_help_str()` (default limit 45) is
used, e.g. shell-completion help (`core.py` L1532). Root cause: `core.py`
`_make_default_short_help` (L1646-1668) compares cumulative word length against
`max_length` directly, never subtracting the 3 chars for `...`.

---

## 11. Implicit `--help` option's parameter name differs in `to_info_dict`  — Low/Medium — channel: to_info / return value

```python
@c.command()
def cli(): pass
ctx = c.Context(cli, info_name="cli")
[p["name"] for p in cli.to_info_dict(ctx)["params"]]
```
- **oracle**: `['_click_default_help']`
- **clirelay**: `['help']`

This affects **every** command/group's `to_info_dict`. The contract normalizer
does not touch it (there is no `clirelay.` dotted prefix). Note the existing
`tests/differential/test_info_dict.py` hides it with an out-of-contract
`text.replace('"_click_default_help"', '"help"')` in its `_norm`, so the suite
does not flag it even though it is a genuine public-API difference.

Root cause: `core.py` `get_help_option` (L1049-1067) constructs `Option(...)`
without the special internal name Click assigns (`_click_default_help`).

---

## 12. `version_option` version-detection error handling differs  — Medium — channel: exit code / exception / stdout

Multiple divergences in the no-explicit-version path:

a) Unresolvable package (no version, none guessable):
```python
@c.command()
@c.version_option()
def cli(): pass
# argv ["--version"]
```
- **oracle**: exit `1`, `RuntimeError("Could not determine the version for None automatically.")`
- **clirelay**: exit `0`, prints `'cli, version 8.5.0'` — it guesses a package and reports a version where Click errors (and the message, when it does raise, says the prog name `'cli'` rather than `None`, and uses `ClickException` not `RuntimeError`).

b) Explicit but missing `package_name`:
```python
@c.version_option(package_name="no_such_pkg_xyz_123")
```
- **oracle**: `RuntimeError("'no_such_pkg_xyz_123' is not installed. Try passing 'package_name' instead.")`
- **clirelay**: leaks raw `importlib.metadata.PackageNotFoundError('no_such_pkg_xyz_123')`

Root cause: `decorators.py` L218-231 — raises `ClickException` with the resolved
prog name instead of `RuntimeError` with the `package_name` value, and does not
wrap `importlib.metadata.version(...)`'s `PackageNotFoundError`.

---

## 13. `echo_via_pager` on a non-terminal drops the trailing newline  — Medium — channel: stdout

Click's non-TTY pager fallback appends a newline; clirelay writes the text
verbatim.

```python
@c.command()
def cli(): c.echo_via_pager("line1\nline2\n")
```
- **oracle**: `'line1\nline2\n\n'`
- **clirelay**: `'line1\nline2\n'`

Consistent one-`\n` shortfall for every input tested (`'abc'`→ oracle `'abc\n'`
vs `'abc'`; `''` → `'\n'` vs `''`; generator inputs likewise). Root cause:
`_term.py` L31-32 — the non-tty branch calls `echo(text, nl=False, ...)`; the TTY
branch (L35) correctly appends `\n`.

---

# Areas probed with NO mismatch found

The following were probed concretely (both via `CliRunner` and direct calls) and
**matched** the oracle after permitted normalization:

- **Parsing**: `--opt=` empty value, `=` with short opts (`-n=val`, `-nval`),
  clustered shorts mixing flags and a value-option (`-abc value`, `-abcvalue`),
  negative-number arguments/values (`-5`, `--n=-5`, `-1.5`), options after `--`,
  `ignore_unknown_options` (incl. `UNPROCESSED` and clustered unknowns),
  `allow_interspersed_args=False`, `allow_extra_args`, `token_normalize_func`
  (commands and option names), option given twice (last wins), empty typed
  values (`--n=`, `--c=`).
- **Envvars**: explicit `envvar`, multi-envvar lists, `multiple` from envvar
  (incl. `os.pathsep` split), flag from envvar across many truthy/falsey values,
  bad int envvar, tuple option from envvar.
- **default_map**: static, nested-group, runtime `ctx.default_map`, bad-type
  validation; `Context.obj` inheritance, `get_parameter_source`
  (DEFAULT/COMMANDLINE/ENVIRONMENT).
- **Types**: `IntRange`/`FloatRange` (clamp, open/closed bounds, messages, help
  `[x<=10]` descriptions, clamp-on-open ctor `TypeError`), `DateTime` custom and
  default formats + help, `Tuple` of mixed types (ok/bad/help), `Choice`
  (case-insensitive, `Enum`, `token_normalize_func`, metavar, bad-value error),
  `BOOL` conversions, `UUID`, `Path` (`exists`/`file_okay`/`dir_okay`/
  `readable`/`writable`/`executable`/`resolve_path`/`allow_dash`/`path_type`
  str/bytes/`pathlib.Path`), `File` (read/encoding/atomic write/`-` round-trips
  aside from findings #2/#3), custom `ParamType.convert`/`fail`.
- **Help/formatting** (at explicit widths 40/60/80/120): `\b` blocks, `\f`
  truncation, epilog (incl. `\b`), `short_help`, hidden commands/options,
  `options_metavar`, long option rows, no-docstring commands, `add_help_option=
  False`, custom `help_option_names` (incl. nested inheritance), command ordering,
  `flag_value` help, deprecated option/command help.
- **Groups**: `CommandCollection`, `chain` (with options, missing args,
  `result_callback`), `invoke_without_command`, `no_args_is_help` (command and
  group), `result_callback`, hidden-but-invokable commands, deprecated commands
  (bool and string, run + warnings).
- **Errors**: missing option/argument/variadic, `nargs=2` wrong count, too-many-
  args, `NoSuchOption` (with/without suggestion), `ClickException`, `FileError`,
  `Abort`, `sys.exit(str|True|None)`, generic exception → exit 1, `ctx.fail`.
- **Decorators**: `version_option` (explicit version / prog_name / custom
  message / on groups), `confirmation_option`, `password_option`, `help_option`,
  `make_pass_decorator(ensure=True)`, `pass_obj`, `is_eager` ordering,
  `expose_value=False` callbacks.
- **Prompts**: default/filled, int retry, `Choice` retry, `confirmation_prompt`
  mismatch, custom `prompt_suffix` via `prompt(...)`, `confirm` (default/garbage/
  n), direct `prompt()` EOF → Abort.
- **CliRunner/Result**: `color=True/False` (ANSI kept/stripped), separate vs
  mixed stderr, `Result.__repr__` (ok and with exception), `catch_exceptions=
  False`.
- **Library funcs**: `style` (fg/bg/bold/dim/underline/blink/reverse/italic/
  strikethrough/overline/256-color/RGB/`reset=False`/bad color), `unstyle`,
  `format_filename` (str/bytes/shorten), `get_app_dir` (incl. posix),
  `wrap_text` (incl. paragraphs/indents), `split_arg_string` (via both
  `parser` — with identical `DeprecationWarning` — and `shell_completion`),
  `get_terminal_size`.
- **Shell completion**: command/option/`Choice`-value completion responses
  (values, types, help) including hidden-command filtering.
- **to_info_dict**: complex command (ranges, choices, file/path, tuple, flag
  pairs, variadic arg) matches apart from finding #11.

---

# Coverage gaps (could NOT be fully verified here)

These were not fully compared and deserve dedicated differential coverage:

1. **Real-PTY terminal helpers**: `getchar`, `pause`, interactive `edit`,
   hidden-input prompts over a real terminal, and the **TTY** rendering of
   `progressbar` and `echo_via_pager` (real pager subprocess). The non-TTY paths
   are covered above (findings #6, #13); the interactive rendering is a no-op in
   clirelay (`_term.py` render stubs) and was not exercised against a PTY.
2. **`max_content_width` / auto-width under a real terminal** (finding #4): the
   `-2`/floor divergence is proven via direct `HelpFormatter`/`get_help`, but the
   exact behavior when run against an actual wide terminal (vs. the 80-col
   CliRunner default) was not measured on both libraries side by side at the OS
   level.
3. **`File(atomic=True)` write semantics**: only the returned object was checked,
   not the temp-file-then-rename behavior, permissions, or failure cleanup.
4. **Windows-specific behavior**: color/ANSI handling, `get_app_dir` roaming
   paths, `_winconsole`-style stream handling — not testable on this macOS host.
5. **`launch`** — exempt (opens real applications).
6. **Completion script bodies** for bash/zsh/fish/pwsh were not diffed here
   (the existing `test_completion.py` covers them); only completion *responses*
   were re-checked.
7. **Deep `to_info_dict` of exotic params** (custom `ParamType` subclasses,
   deprecated params, `flag_value` non-bool) beyond the complex case above.
