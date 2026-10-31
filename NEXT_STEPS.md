# NEXT_STEPS — session handoff

Read `BUILD_PROMPT.md` first (the verbatim task and its rules), then this file.
A new session continues from here under the same rules. Keep this file current.

## Environment

- Oracle: `~/clirelay-oracle` (bytecode-only Click 8.5.0; black box only).
  Override dir with `CLIRELAY_ORACLE_DIR`.
- Python: 3.15 at `/opt/homebrew/opt/python@3.15/bin/python3.15`, magic
  `520e0d0a`. Project venv at `.venv` (created with `uv`).
- `uv` installed via Homebrew. clirelay installed editable; test deps: pytest,
  hypothesis; docs deps: sphinx, myst-parser, furo; tox + tox-uv installed.
- Run everything with: `CLIRELAY_REQUIRE_ORACLE=1 .venv/bin/python -m pytest -rs -p no:warnings`

## Done

- [x] Phase 1 plan + full library (types, parsing, core, decorators, termui,
  testing, shell_completion, utils, globals, formatting, deprecated attrs).
- [x] Differential harness, normalizer (3 rules + tests), oracle loader
  (version/magic guard, CLIRELAY_REQUIRE_ORACLE), oracle-hygiene AST lint.
- [x] API conformance 100%.
- [x] Differential channels: commands, help widths, library functions, prompts,
  completion (scripts + responses), to_info_dict, API misuse, terminal (PTY),
  warnings/deprecation.
- [x] Hypothesis-style fuzz: 22,255 invocations, all matching.
- [x] Repo artifacts: README, LICENSE, CHANGES, pyproject, uv.lock (no click),
  docs (Sphinx+MyST, builds with -W), 10 examples, .github/, devcontainer,
  editorconfig, pre-commit, readthedocs, tox.ini, coverage matrix, unit tests.
- [x] Current: **286 passed, 8 skipped** on Python 3.15.

## Remaining / polish

1. Fresh-review subagent (step 7): run an independence-bound agent to probe for
   coverage gaps; fold in any new cases it finds. (In progress / see
   `tests/differential/` for additions.)
2. Broaden PTY coverage (progressbar rendering is timing-exempt; `pause`,
   `clear`).
3. Optional: `mypy`/`ruff` clean-up pass; add more realistic CLIs to the fuzz
   corpus.
4. Keep PROVENANCE.md pass-rate table current after any change.

## Notes for probing (rules discovered empirically — never from recall)

- Terminal width ignores `COLUMNS` under a runner (os.get_terminal_size on the
  fd, fallback 80); widths are exercised via the `terminal_width` context arg.
- Deprecation notices are echoed to stderr as output (not Python warnings).
- Prompts echo the typed input; errors show `e.message` (bare); hidden invalid
  input is masked `'***'`; stdout is line-buffered / stderr write-through so the
  combined output interleaves like the oracle.
- `did you mean` lists are `sorted(get_close_matches(...))`.
- Pager uses `$PAGER` only when stdout is a tty and appends a trailing newline.
