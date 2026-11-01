# Changelog

## Unreleased

Behavior corrections from a second external evaluation that drove both libraries
through real processes and pseudo-terminals ("Fix round 2"). Each was confirmed
against the reference in all three run modes (CliRunner, piped subprocess,
pseudo-terminal) and is covered in `tests/differential/test_fix_round2.py`.

- Prompts no longer echo the typed answer. The visible echo belongs to
  `CliRunner` (which replaces the prompt reader); a real terminal echoes the
  answer itself, and piped input shows nothing. This applies to `prompt`,
  `confirm`, option prompts, `confirmation_option` and `password_option`.
- Hidden input is read through the public `termui.hidden_prompt_func` (getpass),
  so the typed characters are never displayed.
- `multiple` options read environment variables split by the parameter type
  (`Path`/`File` on `os.pathsep`, strings on whitespace).
- `multiple=True` combined with `nargs>1` produces a tuple of tuples.
- Completion completes only the argument at the cursor position (variadic
  arguments always), with correct ordering and no state leaking between contexts.
- `DateTime` reports "format" (singular) when it has a single format.
- A `ParamType` subclass without a `name` falls back to its class name in
  `to_info_dict`.
- `Context.with_resource` hands the command's exception to the resource's
  `__exit__`; a clean run passes `None`.
- Undecodable bytes in path errors render with the Unicode replacement character.
- `Group` subclass method hooks are called in the same order and number as the
  reference (unknown-subcommand suggestions no longer call `list_commands`).

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
