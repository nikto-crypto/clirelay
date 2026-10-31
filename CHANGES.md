# Changelog

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
