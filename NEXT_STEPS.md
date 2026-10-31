# NEXT_STEPS — session handoff

Read `BUILD_PROMPT.md` first (the verbatim task and its rules), then this file.
A new session continues from here under the same rules. Keep this file current.

## Environment

- Oracle: `~/clirelay-oracle` (bytecode-only Click 8.5.0; black box only).
  Override dir with `CLIRELAY_ORACLE_DIR`.
- Python: 3.15 at `/opt/homebrew/opt/python@3.15/bin/python3.15`, magic
  `520e0d0a`. Project venv at `.venv` (created with `uv`, matches that magic).
- `uv` was installed via Homebrew.
- Full readable API dump: regenerate from `~/clirelay-oracle/API_SURFACE.json`
  (schema in `~/clirelay-oracle/tools/api_surface.py`).

## Done so far

- [x] Phase 1 (plan): `BUILD_PROMPT.md`, venv on oracle Python, `.python-version`,
  `SPEC.md`, `PROVENANCE.md`, repo scaffold (`pyproject.toml`, `LICENSE.txt`,
  `.gitignore`).

## Current pass rates

- API surface conformance: not yet (no library code).
- Differential: not yet (no harness, no library).

## Next, in order

1. Create the `src/clirelay/` package skeleton (all public modules importable,
   even if stubbed) + `py.typed`.
2. Write `tests/differential/normalize.py` (the 3 allowed normalizations) + its
   unit tests; oracle-loading fixture with magic/version guard and
   `CLIRELAY_REQUIRE_ORACLE`; `tests/test_oracle_hygiene.py` AST lint.
3. Write `tests/test_api_surface.py` conformance walker.
4. Implement the library in phases (types → params/parsing → commands → groups/
   context → help → errors → termui → CliRunner → completion → deprecated attrs),
   probing the oracle for each behavioral rule. Commit + record pass rate per
   phase.
5. Hand-written realistic CLIs, Hypothesis generators (≥20k invocations),
   coverage matrix.
6. Repo artifacts: README, CHANGES, docs (Sphinx+MyST), ~10 examples, .github/,
   devcontainer/editorconfig/pre-commit/readthedocs, uv.lock.
7. Fresh-review subagent (independence-bound) to find coverage gaps.

## Open questions / notes for probing

- Confirm exact `to_info_dict` shapes for every ParamType and for Context/Command/
  Parameter by probing the oracle.
- Confirm help-formatting wrap behavior at each width empirically.
- Deprecated attrs resolve to private objects (qualname starts `_`) that behave
  like their public counterparts, each emitting its exact DeprecationWarning
  (texts captured in PROVENANCE/working notes from API_SURFACE.json).
