# Changelog

## Unreleased

Behavior corrections from an external evaluation against the contract ("Fix
round 1"). Each was confirmed against the reference and is covered as a whole
class of inputs in `tests/differential/test_fix_round1.py`.

- `Context.invoke`/`forward` now type-convert the defaults they fill in, while
  leaving explicitly passed values untouched.
- Option prompts re-ask on empty input (with no default), on a conversion
  failure, and when a callback rejects the value.
- Shared-destination feature switches respect which declaration sets the default;
  options with `is_flag=False` and a `flag_value` take an optional value.
- A group with no subcommand (and not `invoke_without_command`) reports
  `Missing command.` rather than printing full help.
- Odd option defaults (sets, dicts, …) infer the `str` type.
- Help fixes: optional Choice arguments show `[a|b]`; an empty-string default
  shows `[default: ""]`; `\b` in option help reflows correctly; wrapping breaks
  after hyphens.
- Help width follows `COLUMNS` in a real process (capped at the max content
  width); `echo` writes UTF-8 bytes to a stream that cannot encode the text
  instead of raising.
- The progress bar renders real terminal frames (only the ETA/speed figures are
  timing-dependent).
- `version_option` detects the distribution from the module applying it.
- Completion no longer re-suggests used single-value options, offers file/dir
  items for `File`/`Path`, completes every value of multi-value options, and
  works with custom `Group` subclasses.

## 8.5.0

Initial release of clirelay: a composable command-line interface toolkit written
from scratch. The version number tracks the behavioral contract this release
implements.

- Commands, groups, chaining, and command collections.
- Options (flags, on/off pairs, counts, multiple, nargs, defaults, required,
  environment variables, prompts, deprecation) and positional arguments
  (including variadic and deprecated arguments).
- Parameter types: string, integer, float, boolean, UUID, unprocessed, choice
  (including `Enum`-backed and case-insensitive), integer and float ranges with
  clamping, tuples, datetimes, files, and paths, plus custom types.
- Terminal-width-aware help rendering, usage lines, and error messages.
- Interactive prompts, confirmations, hidden input, and progress bars.
- Shell completion for bash, zsh, fish, and PowerShell.
- `CliRunner` and `Result` for testing commands in isolation.
- Deprecated module attributes kept for compatibility, each with its warning.
