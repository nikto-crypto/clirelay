"""Shell completion: source scripts and completion responses.

The four shell source scripts must match the oracle byte for byte and live in
``_completion_scripts``.  This module wires those templates to the completion
logic and exposes the registry.  (Fully fleshed out and verified in the
completion phase.)
"""
from __future__ import annotations

import os
import re
import typing as t

from .core import Argument, Command, Context, Group, Option, ParameterSource
from .utils import echo

if t.TYPE_CHECKING:
    from .core import Parameter


class CompletionItem:
    """A single completion suggestion."""

    __slots__ = ("value", "type", "help", "_info")

    def __init__(
        self,
        value: t.Any,
        type: str = "plain",
        help: str | None = None,
        **kwargs: t.Any,
    ) -> None:
        self.value = value
        self.type = type
        self.help = help
        self._info = kwargs

    def __getattr__(self, name: str) -> t.Any:
        return self._info.get(name)

    def __class_getitem__(cls, item: t.Any) -> type:
        return cls


class ShellComplete:
    """Base class for a shell's completion backend."""

    name: str
    source_template: str

    def __init__(
        self,
        cli: Command,
        ctx_args: t.MutableMapping[str, t.Any],
        prog_name: str,
        complete_var: str,
    ) -> None:
        self.cli = cli
        self.ctx_args = ctx_args
        self.prog_name = prog_name
        self.complete_var = complete_var

    @property
    def func_name(self) -> str:
        safe = re.sub(r"\W*", "", self.prog_name.replace("-", "_"), flags=re.ASCII)
        return f"_{safe}_completion"

    def source_vars(self) -> dict[str, t.Any]:
        return {
            "complete_func": self.func_name,
            "complete_var": self.complete_var,
            "prog_name": self.prog_name,
        }

    def source(self) -> str:
        return self.source_template % self.source_vars()

    def get_completion_args(self) -> tuple[list[str], str]:
        raise NotImplementedError

    def get_completions(
        self, args: list[str], incomplete: str
    ) -> list[CompletionItem]:
        ctx = _resolve_context(self.cli, self.ctx_args, self.prog_name, args)
        if ctx is None:
            return []
        obj, incomplete = _resolve_incomplete(ctx, args, incomplete)
        return obj.shell_complete(ctx, incomplete)

    def format_completion(self, item: CompletionItem) -> str:
        raise NotImplementedError

    def complete(self) -> str:
        args, incomplete = self.get_completion_args()
        completions = self.get_completions(args, incomplete)
        out = [self.format_completion(item) for item in completions]
        return "\n".join(out)


class BashComplete(ShellComplete):
    name = "bash"
    from ._completion_scripts import BASH_SOURCE as source_template  # type: ignore[misc]

    def _get_words(self) -> list[str]:
        cwords = split_arg_string(os.environ["COMP_WORDS"])
        cword = int(os.environ["COMP_CWORD"])
        return cwords[1:cword]

    def get_completion_args(self) -> tuple[list[str], str]:
        cwords = split_arg_string(os.environ["COMP_WORDS"])
        cword = int(os.environ["COMP_CWORD"])
        args = cwords[1:cword]
        try:
            incomplete = cwords[cword]
        except IndexError:
            incomplete = ""
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        return f"{item.type},{item.value}"


class ZshComplete(ShellComplete):
    name = "zsh"
    from ._completion_scripts import ZSH_SOURCE as source_template  # type: ignore[misc]

    def get_completion_args(self) -> tuple[list[str], str]:
        cwords = split_arg_string(os.environ["COMP_WORDS"])
        cword = int(os.environ["COMP_CWORD"])
        args = cwords[1:cword]
        try:
            incomplete = cwords[cword]
        except IndexError:
            incomplete = ""
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        return f"{item.type}\n{item.value}\n{item.help if item.help else '_'}"


class FishComplete(ShellComplete):
    name = "fish"
    from ._completion_scripts import FISH_SOURCE as source_template  # type: ignore[misc]

    def get_completion_args(self) -> tuple[list[str], str]:
        cwords = split_arg_string(os.environ["COMP_WORDS"])
        incomplete = os.environ["COMP_CWORD"]
        args = cwords[1:]
        if incomplete and args and args[-1] == incomplete:
            args.pop()
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        if item.help:
            return f"{item.type},{item.value}\t{item.help}"
        return f"{item.type},{item.value}"


class PowerShellComplete(ShellComplete):
    name = "powershell"
    from ._completion_scripts import POWERSHELL_SOURCE as source_template  # type: ignore[misc]

    def get_completion_args(self) -> tuple[list[str], str]:
        cwords = split_arg_string(os.environ["COMP_WORDS"])
        incomplete = os.environ["COMP_CWORD"]
        args = cwords[1:]
        if incomplete and args and args[-1] == incomplete:
            args.pop()
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        return f"{item.value}\t{item.type}\t{item.help or ' '}"


_available_shells: dict[str, type[ShellComplete]] = {
    "bash": BashComplete,
    "zsh": ZshComplete,
    "fish": FishComplete,
    "powershell": PowerShellComplete,
}

_ShellCompleteT = t.TypeVar("_ShellCompleteT", bound="type[ShellComplete]")


def add_completion_class(
    cls: t.Any, name: str | None = None
) -> t.Any:
    if name is None:
        name = cls.name
    _available_shells[name] = cls
    return cls


def get_completion_class(shell: str) -> type[ShellComplete] | None:
    return _available_shells.get(shell)


def split_arg_string(string: str) -> list[str]:
    import shlex

    lex = shlex.shlex(string, posix=True)
    lex.whitespace_split = True
    lex.commenters = ""
    out: list[str] = []
    try:
        for token in lex:
            out.append(token)
    except ValueError:
        # incomplete token (unclosed quote): keep what we have
        remainder = lex.token
        if remainder:
            out.append(remainder)
    return out


def _resolve_context(
    cli: Command,
    ctx_args: t.MutableMapping[str, t.Any],
    prog_name: str,
    args: list[str],
) -> Context | None:
    ctx_args["resilient_parsing"] = True
    with cli.make_context(prog_name, list(args), **ctx_args) as ctx:
        args = ctx._protected_args + ctx.args
        while args:
            command = ctx.command
            if isinstance(command, Group):
                if not command.chain:
                    name, cmd, args = command.resolve_command(ctx, args)
                    if cmd is None:
                        return ctx
                    ctx = cmd.make_context(name, args, parent=ctx, resilient_parsing=True)
                    args = ctx._protected_args + ctx.args
                else:
                    break
            else:
                break
    return ctx


def _resolve_incomplete(
    ctx: Context, args: list[str], incomplete: str
) -> tuple[t.Any, str]:
    if incomplete == "=":
        return ctx.command, ""
    if "=" in incomplete and incomplete[:1] in ctx._opt_prefixes:
        name, _, incomplete = incomplete.partition("=")
        for param in ctx.command.get_params(ctx):
            if isinstance(param, Option) and name in param.opts:
                return param, incomplete
    # If the previous token is an option that still needs a value, complete it.
    if args:
        last = args[-1]
        for param in ctx.command.get_params(ctx):
            if (
                isinstance(param, Option)
                and not param.is_flag
                and not param.count
                and last in [*param.opts, *param.secondary_opts]
            ):
                return param, incomplete
    return ctx.command, incomplete


def shell_complete(
    cli: Command,
    ctx_args: t.MutableMapping[str, t.Any],
    prog_name: str,
    complete_var: str,
    instruction: str,
) -> int:
    shell, _, instruction = instruction.partition("_")
    comp_cls = get_completion_class(shell)
    if comp_cls is None:
        return 1
    comp = comp_cls(cli, ctx_args, prog_name, complete_var)
    if instruction == "source":
        echo(comp.source())
        return 0
    if instruction == "complete":
        echo(comp.complete())
        return 0
    return 1


def _start_completion(
    cli: Command,
    ctx_args: t.MutableMapping[str, t.Any],
    prog_name: str,
    complete_var: str,
) -> bool:
    instruction = os.environ.get(complete_var)
    if not instruction:
        return False
    import sys

    rv = shell_complete(cli, ctx_args, prog_name, complete_var, instruction)
    sys.exit(rv)
