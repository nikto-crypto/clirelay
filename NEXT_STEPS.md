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
- [x] Fresh-review subagent (step 7): 12 fixes + 1 exempt, locked in
  `tests/differential/test_review.py`.
- [x] Fix round 1 (external evaluation): 15 findings confirmed against the oracle
  and fixed; whole-class regressions in `tests/differential/test_fix_round1.py`.
  Includes real `progressbar` terminal rendering (no more stub), `COLUMNS`-driven
  width in a real process, non-UTF-8 `echo`, decoration-time `version_option`
  package detection, and completion for Path/nargs/used-options/custom groups.
- [x] Current: **432 passed, 0 skipped** on Python 3.15.2.

## Remaining / polish

1. Optional: `mypy`/`ruff` clean-up pass; add more realistic CLIs to the fuzz
   corpus.
2. Indeterminate (lengthless) progress bars pulse on a timer and are not asserted
   byte-for-byte (timing-dependent); verify structurally if needed.
3. Windows-only behavior remains unverified on macOS (see `PROVENANCE.md`).
4. Keep PROVENANCE.md pass-rate table current after any change.

## Notes for probing (rules discovered empirically — never from recall)

- Terminal width: under `CliRunner` the forced width of 80 applies; in a real
  process the width follows `COLUMNS` via `shutil.get_terminal_size`, capped at
  `max_content_width` (default 80). Widths are also exercised via the
  `terminal_width` context arg.
- Deprecation notices are echoed to stderr as output (not Python warnings).
- Prompts echo the typed input; errors show `e.message` (bare); hidden invalid
  input is masked `'***'`; stdout is line-buffered / stderr write-through so the
  combined output interleaves like the oracle.
- `did you mean` lists are `sorted(get_close_matches(...))`.
- Pager uses `$PAGER` only when stdout is a tty and appends a trailing newline.
