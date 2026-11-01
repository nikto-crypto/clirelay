# Coverage matrix (features × channels)

Each cell names the differential test(s) that exercise a feature on a channel.
Channels follow `BUILD_PROMPT.md` ("What 'same output' means"):

- **C1** invocation (exit code, stdout, stderr, combined output, return value, escaping exception)
- **C2** values received by callbacks / `to_info_dict` state
- **C3** help & usage text at widths 40/60/80/120
- **C4** error & usage messages on the right stream
- **C5** library functions (return/output/errors)
- **C6** prompts & interaction
- **C7** shell completion (scripts & responses)
- **C8** warnings (categories & messages)
- **C9** public API surface
- **C10** API misuse

Test files (`tests/differential/` unless noted):
`test_commands.py` (TC), `test_generated.py` (TG, 22k+ cases),
`test_library.py` (TL), `test_prompts.py` (TP), `test_completion.py` (TK),
`test_info_dict.py` (TI), `test_misuse.py` (TM), `../test_api_surface.py` (TA),
`../test_oracle_hygiene.py` (TH), `test_terminal.py` (TT), `test_review.py` (TR),
`test_fix_round1.py` (TF), `test_fix_round2.py` (TF2).

TF2 runs every prompt/confirm/password/confirmation case **three ways** —
`CliRunner`, a piped subprocess, and a pseudo-terminal — and all three must match
the oracle. (In a terminal the terminal echoes the typed answer; in a subprocess
nothing does; under `CliRunner` the replaced reader does. The library never
echoes it.)

| Feature | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 |
|---------|----|----|----|----|----|----|----|----|----|-----|
| str/int/float options | TC,TG | TG,TI | TC,TG | TG | TL | — | — | — | TA | — |
| flags (`is_flag`) | TC,TG | TG,TI | TC,TG | — | — | — | TK | — | TA | — |
| `--x/--no-x` pairs | TC,TG | TG,TI | TG | — | — | — | — | — | TA | — |
| shared-destination flags | TG,TF | TG,TF | — | — | — | — | — | — | — | — |
| feature switches (default side) | TF | TF | — | — | — | — | TF | — | — | — |
| optional-value options (flag_value) | TF | TF | — | TF | — | TF | — | — | — | — |
| count options | TC,TG | TG,TI | TC,TG | — | — | — | — | — | TA | — |
| multiple options | TC,TG | TG,TI | TG | — | — | — | — | — | TA | — |
| nargs (fixed/variadic) | TC,TG | TG | TG | TG | — | — | — | — | TA | TM |
| defaults / show_default | TG | TG,TI | TC,TG,TF | — | — | — | — | — | — | — |
| default type inference (odd defaults) | TF | TF | — | — | — | — | — | — | — | — |
| required | TC,TG | TG | TG | TG | — | — | — | — | — | — |
| envvar / auto_envvar | TG | TG | — | — | — | — | — | — | — | — |
| hidden / deprecated options | TC | TI | TC | TC | — | — | TK | TC | — | TM |
| Choice (case/Enum) | TC,TG | TG,TI | TG | TG,TP | TL | TP | TK | — | TA | — |
| IntRange/FloatRange (clamp) | TC,TG | TI | TG | TG | TL | — | — | — | TA | TM |
| Tuple | TG | TI | — | — | TL | — | — | — | TA | — |
| File / Path | — | TI | — | — | TL | — | TF | — | TA | — |
| DateTime / UUID / BOOL | TG | TI | — | TG | TL | — | — | — | TA | — |
| custom ParamType | — | — | — | — | TL (unit) | — | TK | — | TA | — |
| arguments (nargs/required/help) | TC,TG | TG,TI | TC,TG | TG | — | — | TK | TC | TA | TM |
| groups (nested) | TC,TG | TC | TC,TG | TC | — | — | TK | — | TA | — |
| chain / invoke_without_command | TC | TI | TC | TC | — | — | — | — | — | — |
| no_args_is_help / Missing command | TC,TF | — | TC,TF | TC,TF | — | — | — | — | — | — |
| result_callback | TC (imagepipe) | — | — | — | — | — | — | — | — | — |
| custom Group / aliases | TC | — | — | TC | — | — | TF | — | — | — |
| Context / passing objects | TC | TI | — | — | — | — | — | — | TA | TM |
| ctx.invoke / forward delegation | TF | TF | — | — | — | — | — | — | — | — |
| eager callback order | — | TF | — | — | — | — | — | — | — | — |
| help_option_names order | — | — | — | — | TF | — | — | — | TA | — |
| echo / secho / style / unstyle | — | — | — | — | TL | — | — | — | TA | TM |
| wrap_text / HelpFormatter | — | — | TC,TG,TF | — | TL | — | — | — | TA | — |
| help: \b, hyphen wrap, metavars | — | — | TF | TF | — | — | — | — | — | — |
| real-subprocess COLUMNS width | — | — | TF | — | — | — | — | — | — | — |
| non-UTF-8 stdout (echo) | TF | — | — | — | TF | — | — | — | — | — |
| progressbar rendering (PTY) | — | — | — | — | TF | TF | — | — | — | — |
| version_option auto-detect | TF | — | — | — | — | — | — | — | — | TF |
| format_filename / get_app_dir | — | — | — | — | TL | — | — | — | TA | — |
| prompts / confirm / hidden | — | — | — | — | — | TP,TF2 | — | — | TA | — |
| prompt input NOT echoed (3-way) | TF2 | — | — | TF2 | — | TF2 | — | — | — | — |
| hidden input (getpass, 3-way) | TF2 | — | — | TF2 | — | TF2 | — | — | — | — |
| password / confirmation option (3-way) | TF2 | — | — | — | — | TF2 | — | — | — | — |
| prompt err-stream routing (3-way) | — | — | — | TF2 | — | TF2 | — | — | — | — |
| confirmation prompt / retries | — | — | — | — | — | TP,TF,TF2 | — | — | — | — |
| prompt re-ask (empty/invalid/callback) | — | — | — | — | — | TF,TF2 | — | — | — | — |
| multiple + nargs (tuple of tuples) | TF2 | TF2 | — | — | — | — | — | — | — | — |
| envvar list split (Path/File/str) | TF2 | TF2 | — | — | — | — | — | — | — | — |
| DateTime singular/plural message | — | — | — | TF2 | — | — | — | — | — | — |
| name-less ParamType to_info_dict | — | TF2 | — | — | — | — | — | — | — | — |
| Context.with_resource exceptions | TF2 | TF2 | — | — | — | — | — | — | — | — |
| undecodable path bytes (�) | — | — | — | TF2 | TF2 | — | — | — | — | — |
| FloatRange open bounds / clamp | TF2 | — | TF2 | TF2 | — | — | — | — | — | — |
| completion at cursor position | — | — | — | — | — | — | TF2 | — | — | — |
| completion nargs/variadic ordering | — | — | — | — | — | — | TF2 | — | — | — |
| completion no state leak | — | — | — | — | — | — | TF2 | — | — | — |
| Group subclass hook order | — | TF2 | — | — | — | — | TF2 | — | — | — |
| completion scripts (4 shells) | — | — | — | — | — | — | TK | — | TA | — |
| completion responses | — | — | — | — | — | — | TK,TF | — | — | — |
| completion: used opts / nargs / Path | — | — | — | — | — | — | TF | — | — | — |
| split_arg_string | — | — | — | — | TK | — | TK | — | TA | — |
| deprecated attributes | — | — | — | — | — | — | — | TA | TA | — |
| warnings (deprecation/user) | TC | — | — | — | — | — | — | TC,TM | — | TM |
| CliRunner / Result | all | all | all | all | all | TP | TK | — | TA | TM |
| decorator / param misuse | — | — | — | — | — | — | — | — | — | TM |
| oracle hygiene lint | — | — | — | — | — | — | — | — | — | TH |

Notes:

- Terminal-only behaviors are compared through a pseudo-terminal: `edit`
  (via `EDITOR`), `echo_via_pager` (via `PAGER`) and `getchar` in `TT`, and the
  `progressbar` renderer in `TF` (its ETA/speed figures are the only part
  normalized away, since the contract exempts timing). `pause`/`clear` are
  verified structurally.
- Realistic apps combining several of these features (a database CLI, a web
  launcher, a task queue) run in `TF`, alongside the package-manager/web-server/
  git-like/pipeline apps in `TC`.
- Every prompt/confirm/password/confirmation case in `TF2` is checked in all
  three run modes (CliRunner, piped subprocess, pseudo-terminal). The hidden
  path uses the public `clirelay.termui.hidden_prompt_func` (getpass); the
  getpass fallback warning on a non-tty subprocess is identical to the oracle's
  because both import the same standard-library `getpass`.
- `launch` is exempt from testing (opens real applications); it is implemented
  as documented.
- Windows-only behavior is unverified on this machine (see `PROVENANCE.md`).
