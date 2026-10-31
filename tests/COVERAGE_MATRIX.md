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
`../test_oracle_hygiene.py` (TH).

| Feature | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 |
|---------|----|----|----|----|----|----|----|----|----|-----|
| str/int/float options | TC,TG | TG,TI | TC,TG | TG | TL | — | — | — | TA | — |
| flags (`is_flag`) | TC,TG | TG,TI | TC,TG | — | — | — | TK | — | TA | — |
| `--x/--no-x` pairs | TC,TG | TG,TI | TG | — | — | — | — | — | TA | — |
| shared-destination flags | TG | TG | — | — | — | — | — | — | — | — |
| count options | TC,TG | TG,TI | TC,TG | — | — | — | — | — | TA | — |
| multiple options | TC,TG | TG,TI | TG | — | — | — | — | — | TA | — |
| nargs (fixed/variadic) | TC,TG | TG | TG | TG | — | — | — | — | TA | TM |
| defaults / show_default | TG | TG,TI | TC,TG | — | — | — | — | — | — | — |
| required | TC,TG | TG | TG | TG | — | — | — | — | — | — |
| envvar / auto_envvar | TG | TG | — | — | — | — | — | — | — | — |
| hidden / deprecated options | TC | TI | TC | TC | — | — | TK | TC | — | TM |
| Choice (case/Enum) | TC,TG | TG,TI | TG | TG,TP | TL | TP | TK | — | TA | — |
| IntRange/FloatRange (clamp) | TC,TG | TI | TG | TG | TL | — | — | — | TA | TM |
| Tuple | TG | TI | — | — | TL | — | — | — | TA | — |
| File / Path | — | TI | — | — | TL | — | — | — | TA | — |
| DateTime / UUID / BOOL | TG | TI | — | TG | TL | — | — | — | TA | — |
| custom ParamType | — | — | — | — | TL (unit) | — | TK | — | TA | — |
| arguments (nargs/required/help) | TC,TG | TG,TI | TC,TG | TG | — | — | TK | TC | TA | TM |
| groups (nested) | TC,TG | TC | TC,TG | TC | — | — | TK | — | TA | — |
| chain / invoke_without_command | TC | TI | TC | TC | — | — | — | — | — | — |
| no_args_is_help | TC | — | TC | TC | — | — | — | — | — | — |
| result_callback | TC (imagepipe) | — | — | — | — | — | — | — | — | — |
| custom Group / aliases | TC | — | — | TC | — | — | — | — | — | — |
| Context / passing objects | TC | TI | — | — | — | — | — | — | TA | TM |
| echo / secho / style / unstyle | — | — | — | — | TL | — | — | — | TA | TM |
| wrap_text / HelpFormatter | — | — | TC,TG | — | TL | — | — | — | TA | — |
| format_filename / get_app_dir | — | — | — | — | TL | — | — | — | TA | — |
| prompts / confirm / hidden | — | — | — | — | — | TP | — | — | TA | — |
| confirmation prompt / retries | — | — | — | — | — | TP | — | — | — | — |
| completion scripts (4 shells) | — | — | — | — | — | — | TK | — | TA | — |
| completion responses | — | — | — | — | — | — | TK | — | — | — |
| split_arg_string | — | — | — | — | TK | — | TK | — | TA | — |
| deprecated attributes | — | — | — | — | — | — | — | TA | TA | — |
| warnings (deprecation/user) | TC | — | — | — | — | — | — | TC,TM | — | TM |
| CliRunner / Result | all | all | all | all | all | TP | TK | — | TA | TM |
| decorator / param misuse | — | — | — | — | — | — | — | — | — | TM |
| oracle hygiene lint | — | — | — | — | — | — | — | — | — | TH |

Notes:

- Terminal-only behaviors (`getchar`, `pause`, `clear`, `progressbar`,
  `echo_via_pager`, `edit`, hidden-prompt PTY paths) are exercised through the
  `_term` implementation and the examples; full PTY comparison is listed as
  partially verified in `PROVENANCE.md`.
- `launch` is exempt from testing (opens real applications); it is implemented
  as documented.
- Windows-only behavior is unverified on this machine (see `PROVENANCE.md`).
