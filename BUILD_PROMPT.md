# Task

Build `clirelay`, a new Python library that does exactly what Click 8.5.0 (the PyPI release) does, written from scratch with its own design. It is the AI-assisted test group in a research study, with Click 8.5.0 as the control. After you finish, someone else will check two things, using tools and test inputs you won't see:

1. **Same function.** Given the same code and the same input, clirelay produces the same output as Click 8.5.0, as defined below.
2. **Unique code.** clirelay's source shares no code with Click, which will be measured with standard code-similarity tools.

This is a large library (Click is roughly 12,000 lines), and the build will likely need more than one session. Work in the phases under "How to work", commit after each one, and keep NEXT_STEPS.md current: what's done, the current pass rates, and exactly what comes next. If the session ends or the context runs short, a new session continues from NEXT_STEPS.md under these same rules. Keep going until every item under "Done means" is met, and don't stop for progress check-ins.

# Independence rules (no exceptions, and they bind every subagent you start)

- Never look at Click's source code, tests, docs, examples or repo, by any route: site-packages, inspect, dis or any disassembler or decompiler, downloading a package, GitHub, the Pallets documentation site, code search, mirrors, or web pages that quote it. Click's docs and examples contain code, so they are off limits too. The guard settings block the obvious routes. The rest is on you, including web searches that would return Click source or docs, and the session transcript will be audited.
- Your memory of Click is mostly of older releases (the 8.1 era), and many behaviors changed in 8.2 through 8.5: error wording, CliRunner, deprecation handling, Enum choices, help sections. A previous AI build matched Click 8.1.8 far better than 8.5.0 for exactly this reason. Never trust recall. The oracle and the API surface file are the only authorities. Don't write code from memory of Click either. If you notice yourself recalling its implementation, stop, note it in PROVENANCE.md, and take a different approach.
- Choose your own architecture. The public module paths are fixed by the contract (listed below). Everything behind them, including private modules, class internals, helper names, and how the work is split up, is yours. Don't reproduce Click's private module layout or private names.
- Don't copy Click's README, docstrings, docs, or other prose. Write everything in your own words.
- Don't disguise code or pad it. No exec, eval, compile, `marshal.loads`, embedded or encoded code, dynamic imports of the oracle, dead code, or filler written to change how the source looks. Similarity is judged on the library package alone.
- Use the oracle only as a black box. It is a bytecode-only install of Click 8.5.0 in ~/clirelay-oracle (location overridable with the environment variable `CLIRELAY_ORACLE_DIR`).
  - Test code may put that folder on sys.path, import click, and use its public API to define commands and call functions, then compare the results with clirelay doing the same.
  - Read ~/clirelay-oracle/API_SURFACE.json for the public names, kinds, and signatures.
  - Never inspect the oracle any other way: no `help()`, `__doc__`, `dir()`, `vars()`, `__dict__`, underscore attributes, `__annotations__`, pickle or copy of oracle objects, traceback frames, pydoc, `inspect` (beyond what the API surface file gives you), or reading files under ~/clirelay-oracle/click. Add an AST lint to the test suite that fails on these patterns applied to oracle objects.
  - Wrap every oracle call so errors are recorded only as (exception class name, message). Never print an oracle traceback, and run pytest with `-p no:warnings` so warning summaries don't print oracle file names and line numbers.
  - The only copy of click anywhere in your environment is the oracle. No dependency may pull click in (black, sphinx-autobuild, pip-tools and `hypothesis[cli]` all do, so don't use them). uv.lock must not contain click, and the harness must assert that `click.__file__` is under the oracle folder.
  - The library must never import or locate the oracle, and must not embed tables of output captured from it. The one exception is the shell completion source scripts, which must match byte for byte. Reproduce those from the oracle's `source()` output, keep them in a single module, and list it in PROVENANCE.md so the similarity check can treat it separately.
- Don't put "click" in the name of any file or folder you create. The guard blocks reading such paths, including your own.
- Any standard library module is allowed. No third-party runtime dependencies. Overlap that the shared public API forces, such as names, parameter lists, error message text, and use of standard library modules, is expected and fine.

# What "same output" means

For the same program and the same input, clirelay must match Click 8.5.0 on every channel below. The harness may apply only these normalizations, and no others:

- the dotted module prefix `click.` is treated as `clirelay.`;
- memory addresses (`0x` followed by hex digits) are masked;
- warning file names and line numbers are dropped.

All other text must match verbatim, including messages that mention "Click" by name, such as deprecation notices. Keep the normalizer in one small function with its own tests. The oracle defines the contract, including its oddities. Don't fix or improve anything. Run every comparison in a fixed environment: set `COLUMNS`, `HOME`, the XDG variables, and `TERM` to fixed values, unset `NO_COLOR`, and pass an explicit terminal width and color setting.

Public classes must report their public module in `__module__` (for example `clirelay.core.Context`), whatever private module defines them, so reprs match after normalization. `clirelay.__version__` returns clirelay's own installed version, and its deprecation warning names `importlib.metadata.version("clirelay")`. Otherwise its text is verbatim.

1. **Invocations.** For a command run through CliRunner and as a real subprocess (with `COLUMNS` and the environment fixed): exit code, stdout, stderr, the combined output, `return_value` with `standalone_mode=False`, and any escaping exception (class and message).
2. **What the program receives.** The values passed to callbacks, with equal values and types; `ctx.params`, `ctx.args`, `ctx.obj`; `get_parameter_source` results; and the order and number of callback, `result_callback`, and `get_command` calls.
3. **Help and usage text,** exactly, at terminal widths of 40, 60, 80, and 120 and with `max_content_width` set.
4. **Error and usage messages,** exactly, on the right stream.
5. **Library functions.** Return values, written output, and errors of the public functions and classes: `echo`, `secho`, `style`, `unstyle`, `wrap_text`, `HelpFormatter`, every ParamType's `convert`, `get_metavar` and `to_info_dict`, `Context`/`Command`/`Parameter` `to_info_dict`, `format_filename`, `get_app_dir`, `open_file`, the File/Path types, `get_current_context`, and the repr of public objects.
6. **Prompts and interaction.** `prompt`, `confirm`, option prompts, confirmation prompts, hidden input, retries and abort behavior under CliRunner input. For terminal-only behavior (`getchar`, `pause`, `clear`, `progressbar`, `echo_via_pager`, `edit`, hidden prompts), compare through a pseudo-terminal (Python's `pty` module) and through `EDITOR`/`PAGER` pointed at small logging scripts. `launch` would open real applications, so it's exempt from testing; implement it as documented. Anything you can't test goes into the report as unverified.
7. **Shell completion.** The exact source script for `bash`, `zsh`, `fish`, and `powershell` for any program name and completion variable, and the completion responses for given words and cursor positions.
8. **Warnings.** The same warning categories and messages, raised in the same situations (DeprecationWarning, UserWarning). Warning counts and locations are exempt, because they depend on internal call structure. Deprecation notices that Click writes to stderr are output, covered by channel 1.
9. **Public API surface.** The same module paths (`click.X` becomes `clirelay.X`, with the submodules `core`, `decorators`, `exceptions`, `formatting`, `globals`, `parser`, `shell_completion`, `termui`, `testing`, `types`, and `utils`), with the same kind and the same parameter names, order, kinds, and defaults. **Required:**
   - every name exported by top-level `click`;
   - every public class in `click.core`, `click.types`, `click.exceptions`, and `click.shell_completion`, with its public methods and properties;
   - `click.testing.CliRunner` and `Result`;
   - `click.formatting.HelpFormatter` and `wrap_text`;
   - the deprecated module attributes with their exact warnings, each resolving to an object that behaves like its public counterpart;
   - enum members (ParameterSource is an IntEnum: PROMPT=1, COMMANDLINE=2, ENVIRONMENT=3, DEFAULT_MAP=4, DEFAULT=5) and generic subscripting (`ParamType[str]`).

   Everything else in API_SURFACE.json is reference only: match it if it's easy, but it's not required.
10. **API misuse.** Errors raised when the API is used wrongly, such as decorator misuse, invalid parameter declarations, and bad `nargs`/`default` combinations: the same class and message, including AssertionError messages.

## Exempt from parity

These are exempt so you don't have to copy internal structure:

- type annotations in signatures, and the repr of sentinel default values;
- names under a submodule in API_SURFACE.json whose `defined_in` points to a different module (they are imports), TypeVar names (F, R, T, V and similar), and internal helpers such as StreamMixer, BytesIOCopy, EchoingStdin, iter_params_for_processing, augment_usage_errors, measure_table, and iter_rows;
- the internal name Click gives its default help parameter (`_click_default_help` in `to_info_dict`); yours may differ only in that string;
- the wording of TypeError messages that name Click's private functions or classes, as long as the class matches and the error happens in the same situations;
- RecursionError, provided clirelay succeeds wherever Click succeeds;
- Windows-only behavior, which can't be verified on this machine. Implement your best reading of it and list it as unverified;
- timing-dependent numbers in progress bars (elapsed time, ETA, speed);
- how many separate write() calls reach a stream.

## Known traps (verified against Click 8.5.0)

This list is not complete. Commands run through CliRunner at terminal width 80. Usage errors exit 2, write nothing to stdout, and write to stderr as `Usage: <usage line>\nTry '<prog> --help' for help.\n\nError: <message>\n` unless an item says otherwise.

**Errors and messages**

- Unknown option, where `--sort` is the only option: `No such option '--sot'. Did you mean '--sort'?`
- Unknown option, where the command has `--sort` and `--port`: `--sor` gives `No such option '--sor'. (Did you mean one of: '--port', '--sort'?)`
- Unknown option, no close match: `No such option '--zzz'.`
- An option missing its value writes only `Error: Option '--port' requires an argument.\n`, with no Usage or Try lines. Passing a value to a flag (`--a=1`) does the same: `Error: Option '--a' does not take a value.\n`.
- `Missing option '--req'.` / `Missing argument 'SRC'.` / `Got unexpected extra argument (extra)` / `No such command 'sbu'. Did you mean 'sub'?`
- With `show_envvar=True`: `Missing option '--x' (env var: 'XX').`
- A missing required Choice argument: `Missing argument '{a|b}'. Choose from:\n\ta,\n\tb` (no final period), and the usage line shows `{a|b}`.
- With `help_option_names=['-h', '--help']`, the hint still says `Try 'hh --help' for help.`
- A group invoked with no subcommand, and a group with `no_args_is_help=True` invoked with no arguments, write the full help to stderr and exit 2, with nothing on stdout.
- IntRange: `'3.14' is not a valid integer range.` and `11 is not in the range 0<=x<=10.`
- A case-insensitive Choice reports in lowercase: `Choice(['Blue'], case_sensitive=False)` rejects `'1'` with `'1' is not 'blue'.`
- BOOL rejects `'maybe'` with `'maybe' is not a valid boolean. Recognized values: , 0, 1, f, false, n, no, off, on, t, true, y, yes`, and `BOOL.convert('', None, None)` returns False.
- UUID strips input before reporting: `" 7 "` gives `'7' is not a valid UUID.`
- DateTime lists its formats: `'yesterday' does not match the formats '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'.`

**Aborting and prompts**

- `Abort` writes `Aborted!` to stderr and exits 1. KeyboardInterrupt writes `\nAborted!`. A prompt that hits end of input writes the prompt (`X: `) to stdout, then `Aborted!` to stderr, and exits 1.
- A confirmation-prompt mismatch prints `Error: The two entered values do not match.` on stdout and prompts again.
- A hidden prompt with invalid input masks the value: `Pw: \nError: '***' is not a valid integer.\n`, then prompts again.
- A Choice prompt shows its choices, `Color (r, g): `, and rejects `x` with `Error: 'x' is not one of 'r', 'g'.`. `confirm(default=None)` shows `[y/n]` and answers bad input with `Error: invalid input`, looping.
- `sys.exit('bye')` in a command gives exit code 1 with `bye` on stdout under CliRunner, and on stderr in a real subprocess. `raise SystemExit(True)` makes CliRunner's `exit_code` the value `True`.
- Piping to a closed reader (`cli | head -1` with lots of output) exits 1 with empty stderr. SIGINT in a subprocess gives `\nAborted!` and exit 1.
- An envvar with a bad value for a flag: `FF=garbage` gives `Invalid value for '--f': 'garbage' is not a valid boolean. Recognized values: ...`. An unknown completion shell (`_CLI_COMPLETE=nushell_source`) exits 1 and prints nothing.

**Context and decorators**

- `make_pass_decorator(Repo)` with no such object raises `RuntimeError: Managed to invoke callback without a context object of type 'Repo' existing.`
- `get_current_context()` outside a command raises `RuntimeError: There is no active click context.`
- Duplicate parameter names emit `UserWarning: The parameter -a is used more than once. Remove its duplicate as parameters should be unique.`
- An argument `x` alongside an option `--x` emits a UserWarning that begins `The name 'x' is used by an argument and another parameter`, and running `a --x b` gives `'a'`.
- `CliRunner.isolated_filesystem` warns `'isolated_filesystem' is deprecated and will be removed in Click 9.0. Use 'tempfile.TemporaryDirectory' or pytest's 'tmp_path' fixture with absolute paths instead.`
- `custom_version_option(callback, *param_decls, **kwargs)` exists (new in 8.5.0).
- `command(f, cls=Command)` raises `AssertionError: Use 'command(cls=cls)(callable)' to specify a class.` Converting a callback twice raises `TypeError: Attempted to convert a callback into a command twice.`
- A failed subcommand lookup calls `get_command` exactly once.
- A function named `init_cmd` becomes the command `init`.
- `Option(['--q'], deprecated=True, required=True)` raises `ValueError: The option 'q' is deprecated and still required. A deprecated option cannot be required.`
- `style('x', fg=0)` returns `'\x1b[38;5;0mx\x1b[0m'`, and `fg='nope'` raises `ValueError: Unknown color 'nope'`.
- reprs: a command prints as `<Command name>`, and `BOOL` as `BOOL`.

**Parsing**

- With shared-destination flags, the default comes from the declaration that sets one. With `--livereload` (`flag_value=True, default=True`) and `--no-livereload` (`flag_value=False`) on the same destination, no arguments gives True.
- An Enum-backed `Choice(Color)` accepts member *names*, rejects values with `'b' is not one of 'RED', 'BLUE'.`, and shows `[RED|BLUE]` in help.

**Help text**

- `@argument(..., help='The name.')` is supported, and arguments with help get a `Positional arguments:` section before `Options:`.
- Deprecated options are labeled `Old. (DEPRECATED)` and `Older. (DEPRECATED: use --new)`. Using one writes `DeprecationWarning: The option 'old' is deprecated.` to stderr. A deprecated command writes `DeprecationWarning: The command 'depc' is deprecated.`
- `\b` paragraphs keep their line breaks, `\f` cuts off the rest of the help, and a long command help is truncated in group listings with `...`.
- Group usage lines depend on flags:
  - plain `chain=True`: `Usage: ch [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...`
  - `chain=True` with `invoke_without_command=True`: `Usage: ch [OPTIONS] [COMMAND1] [ARGS]... [COMMAND2 [ARGS]...]...`
  - `invoke_without_command=True` alone: `Usage: iw [OPTIONS] [COMMAND] [ARGS]...`
- A deprecated optional argument appears as `[SRC!]` in usage and as the row `[SRC!]  (DEPRECATED)`, and using it writes `DeprecationWarning: The argument 'SRC' is deprecated.` to stderr. In 8.5.0 the `Positional arguments:` section lists only arguments that have help, and the deprecation label counts as help.
- In group listings, the short help is cut at the first sentence end: a docstring `"Does e.g. things."` is listed as `Does e.g.`.
- With a real subprocess, `COLUMNS=120` still caps help lines at 80 (the default `max_content_width`). CliRunner's `terminal_width=120` doesn't cap.
- Run as `python -m mytool`, the program name is `python -m mytool` in usage and hint lines.
- `version_option('1.2', prog_name='p')` prints `p, version 1.2`.

**API**

- `ParamType` is subscriptable, so `class URL(click.ParamType[str])` works.
- `CliRunner(charset, env, echo_stdin, catch_exceptions, capture)` has no `mix_stderr`. `Result` has `output` (stdout and stderr interleaved), `stdout`, `stderr`, `output_bytes`, `stdout_bytes`, `stderr_bytes`, and `return_value`.
- `Option(['--flag/--no-flag'], default=True).to_info_dict()` gives `{'name': 'flag', 'param_type_name': 'option', 'opts': ['--flag'], 'secondary_opts': ['--no-flag'], 'type': {'param_type': 'Bool', 'name': 'boolean'}, 'required': False, 'nargs': 1, 'multiple': False, 'default': True, 'envvar': None, 'help': None, 'prompt': None, 'is_flag': True, 'flag_value': True, 'count': False, 'hidden': False}`.

# How to work

1. **Plan.** Save this prompt verbatim as BUILD_PROMPT.md, so later sessions can read it. Create the project environment on the oracle's interpreter: run `uv venv --python <path>`, where the path is the second line of ~/clirelay-oracle/ORACLE_PYTHON.txt, and write that interpreter's version to `.python-version`. Then write SPEC.md in your own words: the contract, your architecture, and the test strategy.
2. **Check the API surface first.** Write a conformance test that walks API_SURFACE.json and checks every required name, kind, and signature in clirelay. It fails until the build is complete.
3. **Build the differential harness before the library.** `tests/differential/` runs the same program against clirelay and the oracle and compares every channel above. It runs only on the Python minor version and bytecode magic number recorded in ~/clirelay-oracle/ORACLE_PYTHON.txt. It skips when the oracle is missing or the version doesn't match, but setting `CLIRELAY_REQUIRE_ORACLE=1` must turn every such skip into a failure. Feed it:
   - **Hypothesis-generated command specs,** built identically against both libraries: options (flags, `--x/--no-x` pairs, shared-destination flags, counts, multiple, nargs, defaults, required, envvar and `auto_envvar_prefix`, `show_default`, hidden, deprecated, prompts), every ParamType (Choice with case sensitivity and Enums, IntRange and FloatRange with clamping, Tuple, File, Path, DateTime, UUID, BOOL, a custom ParamType), arguments (nargs, required, help), and groups (nested, `chain`, `invoke_without_command`, `no_args_is_help`, `result_callback`, aliases through custom Group classes);
   - **Hypothesis-generated argv for each spec:** valid input, typos, missing values, extra arguments, `--`, `=` syntax, clustered short options, unknown options, bad types, and environment variables;
   - **help rendering** at each width, with `\b`, `\f`, long text, epilogs, and `short_help`;
   - **a suite of realistic CLIs you write yourself,** in the style of common real tools (package managers, web-server launchers, git-like multi-command tools, data pipelines), none copied from anywhere;
   - **prompts with scripted input,** completion requests for each shell, every library function, and API misuse cases;
   - **the deprecated attributes and every DeprecationWarning and UserWarning path.**

   Keep a coverage matrix (features by channels) in the repo and fill every cell with real cases. A large case count made of trivial cases doesn't count.
4. **Implement in phases until the harness shows zero mismatches:** types, parameters and parsing, commands, groups and context, help formatting, errors, terminal utilities, CliRunner, shell completion, then the deprecated attributes. After each phase, commit and record the differential pass rate in PROVENANCE.md. When something differs, find the general rule by probing the oracle with smaller programs. Never special-case a test input.
5. **Write original unit tests** with their own assertions, so the suite stands on its own without the oracle.
6. **Create the repo artifacts** below.
7. **Get a fresh review.** Ask a subagent that hasn't seen this conversation, and is bound by the same independence rules, to look for channels, options, parameter types, or input classes the harness doesn't cover, and add what it finds.

# Repo artifacts (the same set as the Click repo, your own content throughout)

- **README.md**
- **LICENSE.txt:** MIT, copyright Nick Serapiglia.
- **CHANGES.md**
- **pyproject.toml:** flit_core backend, `requires-python >=3.10`, no runtime dependencies, dependency groups for dev, docs, tests, and typing.
- **uv.lock:** generated with uv.
- **src/clirelay/,** with `py.typed`.
- **tests/**
- **docs/:** a Sphinx + MyST site in your own words and with your own examples. It must build without errors, and it covers these topics: quickstart, commands and groups, options, arguments, parameter types, prompts, help and documentation formatting, the context and passing objects, exceptions and exit codes, shell completion, testing with CliRunner, terminal utilities, and an API reference.
- **examples/:** about ten example apps of your own design covering the same feature areas Click's examples cover (command aliases, colors, shell completion, a complex multi-command app, an image-style processing pipeline, file input and output, a game-style nested app, a repository-style tool, terminal UI, and validation). Write them fresh; don't recall Click's.
- **.github/:** issue templates (bug report, feature request, config), a pull request template, and workflows for tests on Python 3.10 to 3.15, pre-commit, a publish workflow triggered only by manual dispatch, and a lock-file update.
- **.devcontainer/, .editorconfig, .gitignore, .pre-commit-config.yaml, .readthedocs.yaml**
- **PROVENANCE.md:** the model and version, the dates, every information source consulted, the pass rate after each phase, and every moment the independence rules came close to being broken.
- **SPEC.md**

The README must explain how to build the oracle and run the differential suite, so the evidence can be reproduced from the repo.

Commit as you go with Conventional Commit messages.

# Done means

Report with evidence, meaning each command and its actual output rather than a summary:

- the full pytest run on the oracle's Python version, with `CLIRELAY_REQUIRE_ORACLE=1`, `-rs` and `-p no:warnings`, showing zero skipped differential tests and the interpreter version. Other Python versions run the unit tests only;
- API surface conformance at 100%;
- the number of generated cases: at least 20,000 command invocations, plus every library-function and completion test;
- a per-channel differential table with zero mismatches. Any remaining mismatch, listed with a minimal repro, means not done;
- tox results for every Python version installed on this machine;
- the docs build output, and each example app run once;
- grep output showing that the library never imports click, never references the oracle folder, and that uv.lock contains no click;
- the coverage matrix with every cell filled.

Don't run any code-similarity tool. That check, and a final differential run on inputs you haven't seen, happen separately.
