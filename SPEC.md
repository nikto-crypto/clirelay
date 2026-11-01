# clirelay — specification and build plan

This document describes, in my own words, what clirelay is, how it is
organized, and how its behavior is verified. It is written for the research
study whose rules live in `BUILD_PROMPT.md`.

## 1. What clirelay is

clirelay is a command-line interface toolkit. A developer decorates a Python
function to turn it into a *command*, decorates it further to attach *options*
and *arguments*, and groups commands into a tree. clirelay parses `argv`,
converts and validates each value, calls the function with the parsed values,
renders `--help` text, reports usage errors, drives interactive prompts, and
emits shell-completion scripts.

The functional contract is defined entirely by an *oracle*: a bytecode-only
install of Click 8.5.0 under `~/clirelay-oracle`. For the same program and the
same input, clirelay must produce the same observable results as the oracle on
every channel listed in `BUILD_PROMPT.md` ("What 'same output' means"). clirelay
is written from scratch; the oracle is consulted only as a black box, never read.

## 2. Public surface (fixed by the contract)

The importable surface mirrors the oracle's public API. Top-level `clirelay`
re-exports the same names the oracle's top-level `click` exports, and these
submodules exist with the same public names, kinds, and signatures:

`core`, `decorators`, `exceptions`, `formatting`, `globals`, `parser`,
`shell_completion`, `termui`, `testing`, `types`, `utils`.

The authoritative list of required names/kinds/signatures is
`~/clirelay-oracle/API_SURFACE.json`. A conformance test
(`tests/test_api_surface.py`) walks that file and checks clirelay against it.

Public classes report their *public* module in `__module__` (e.g.
`clirelay.core.Context`) so that reprs match after the harness normalization that
rewrites the dotted prefix `click.` to `clirelay.`.

## 3. Architecture (mine, not the oracle's)

Public classes are defined directly in their public module so `__module__` is
correct without juggling. Internal helpers live in private modules whose names
are deliberately unlike the oracle's private layout.

Public modules:

- `__init__.py` — re-exports the public names; hosts the module-level
  `__getattr__` that serves deprecated attributes with their warnings and
  `__version__`.
- `core.py` — `Context`, `Command`, `Group`, `CommandCollection`, `Parameter`,
  `Option`, `Argument`, `ParameterSource`, plus the private deprecated bases.
- `types.py` — `ParamType` and all concrete parameter types; `convert_type`.
- `exceptions.py` — the exception hierarchy (`ClickException` … `Abort`, `Exit`).
- `formatting.py` — `HelpFormatter`, `wrap_text`, table/measurement helpers.
- `parser.py` — the public argv parser plus its deprecated attribute shims.
- `shell_completion.py` — `ShellComplete` and the four shell backends,
  `CompletionItem`, registry functions, `shell_complete`, `split_arg_string`.
- `termui.py` — `prompt`, `confirm`, `echo_via_pager`, `progressbar`, `getchar`,
  `pause`, `clear`, `edit`, `launch`, `style`, `secho`, `unstyle`, …
- `testing.py` — `CliRunner`, `Result`, stream plumbing.
- `utils.py` — `echo`, `get_app_dir`, `format_filename`, `open_file`, stream
  helpers, plus deprecated attribute shims.
- `globals.py` — the context stack (`get_current_context`, push/pop,
  `resolve_color_default`).
- `decorators.py` — `command`, `group`, `option`, `argument`, the pass
  decorators, the eager helper options.

Private modules (my names, unlike the oracle's):

- `_sentinel.py` — singleton sentinels (unset default / flag-needs-value).
- `_streams.py` — binary/text stream acquisition and wrapping (my analog of the
  oracle's compatibility layer).
- `_ansi.py` — ANSI style codes, `strip_ansi`, color-strip decisions.
- `_term.py` — terminal-only machinery: `getchar`, pager, editor, the progress
  bar renderer.
- `_wrap.py` — the wrapping engine used by `wrap_text` / `HelpFormatter`.
- `_completion_scripts.py` — the four shell source templates, reproduced byte
  for byte from the oracle's `source()` output. **This is the single module
  allowed to match the oracle verbatim** (see `BUILD_PROMPT.md`); it is listed
  in `PROVENANCE.md` so the similarity check treats it separately.

## 4. Test strategy

- **API conformance** (`tests/test_api_surface.py`): walks `API_SURFACE.json`,
  asserts every required name exists with the right kind, parameter
  names/order/kinds/defaults, enum members, subscriptability, and deprecated
  attribute warnings. Fails until the build is complete.
- **Differential harness** (`tests/differential/`): builds the *same* program
  against both libraries and compares every channel (invocation streams/exit
  codes, callback-received values, help/usage text at widths 40/60/80/120,
  errors, library-function results, prompts via scripted input and a PTY,
  completion scripts and responses, warnings, API-misuse errors). It runs only
  when the live interpreter's minor version and bytecode magic match
  `ORACLE_PYTHON.txt`; it skips otherwise, but `CLIRELAY_REQUIRE_ORACLE=1`
  converts every such skip into a failure. The oracle is always used as a black
  box, and every oracle call is wrapped so only `(exception class, message)` is
  recorded — never a traceback.
- **Oracle hygiene**: an AST lint (`tests/test_oracle_hygiene.py`) fails if test
  code introspects oracle objects (`help`, `dir`, `vars`, `__dict__`, underscore
  attributes, `inspect`, pickle/copy, …). The harness also asserts
  `click.__file__` is under the oracle folder.
- **Normalizer** (`tests/differential/normalize.py`): the single small function
  applying only the three allowed normalizations, with its own unit tests.
- **Generators**: Hypothesis builds command specs (options of every shape, every
  ParamType, arguments, groups with chain/invoke_without_command/etc.) and argv
  for each spec (valid, typos, missing values, extras, `--`, `=`, clustered
  shorts, unknown options, bad types, env vars). Target ≥ 20,000 invocations.
- **Hand-written realistic CLIs** exercise whole-app behavior.
- **Unit tests** assert clirelay's behavior directly, so the suite stands alone
  without the oracle.
- A **coverage matrix** (features × channels) in `tests/COVERAGE_MATRIX.md` is
  filled with real cases.

## 5. Build phases

Implement until the harness shows zero mismatches, committing after each phase
and recording the differential pass rate in `PROVENANCE.md`:

1. types
2. parameters and parsing
3. commands
4. groups and context
5. help formatting
6. errors
7. terminal utilities
8. CliRunner
9. shell completion
10. deprecated attributes

When behavior differs, the general rule is found by probing the oracle with
smaller programs — never by special-casing a test input.
