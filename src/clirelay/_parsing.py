"""The command-line argument parser.

This is clirelay's own getopt-style engine.  It resolves option tokens to the
parameters that registered them, collects their values, and leaves positional
tokens for the arguments to distribute.  It deals only in strings; conversion and
validation happen afterwards in the parameter objects.
"""
from __future__ import annotations

import typing as t

from ._sentinel import FLAG_NEEDS_VALUE
from .exceptions import BadArgumentUsage, BadOptionUsage, NoSuchOption, UsageError

if t.TYPE_CHECKING:
    from .core import Argument as CoreArgument
    from .core import Context, Option as CoreOption, Parameter


def split_opt(opt: str) -> tuple[str, str]:
    """Split an option token into its prefix and the remaining name."""
    first = opt[:1]
    if first.isalnum():
        return "", opt
    if opt[1:2] == first:
        return opt[:2], opt[2:]
    return first, opt[1:]


def normalize_opt(opt: str, ctx: Context | None) -> str:
    if ctx is None or ctx.token_normalize_func is None:
        return opt
    prefix, value = split_opt(opt)
    return f"{prefix}{ctx.token_normalize_func(value)}"


class _State:
    __slots__ = ("opts", "largs", "rargs", "order")

    def __init__(self, rargs: list[str]) -> None:
        self.opts: dict[str, t.Any] = {}
        self.largs: list[str] = []
        self.rargs = rargs
        self.order: list[Parameter] = []


class _Option:
    def __init__(
        self,
        obj: CoreOption,
        opts: t.Sequence[str],
        dest: str | None,
        action: str | None = None,
        nargs: int = 1,
        const: t.Any = None,
        optional_value: bool = False,
    ) -> None:
        self.obj = obj
        self.dest = dest
        self.action = action or "store"
        self.nargs = nargs
        self.const = const
        self.optional_value = optional_value
        self._short_opts: list[str] = []
        self._long_opts: list[str] = []
        self.prefixes: set[str] = set()
        for opt in opts:
            prefix, _ = split_opt(opt)
            if len(prefix) == 1 and len(opt) == 2:
                self._short_opts.append(opt)
            else:
                self._long_opts.append(opt)
            self.prefixes.add(prefix)

    @property
    def takes_value(self) -> bool:
        return self.action in ("store", "append")

    def process(self, value: t.Any, state: _State) -> None:
        if self.action == "store":
            state.opts[self.dest] = value
        elif self.action == "store_const":
            state.opts[self.dest] = self.const
        elif self.action == "append":
            state.opts.setdefault(self.dest, []).append(value)
        elif self.action == "append_const":
            state.opts.setdefault(self.dest, []).append(self.const)
        elif self.action == "count":
            state.opts[self.dest] = state.opts.get(self.dest, 0) + 1
        else:
            raise ValueError(f"unknown action {self.action!r}")
        state.order.append(self.obj)


class _Argument:
    def __init__(self, obj: CoreArgument, dest: str | None, nargs: int = 1) -> None:
        self.obj = obj
        self.dest = dest
        self.nargs = nargs

    def process(self, value: t.Any, state: _State) -> None:
        if self.nargs > 1:
            holes = sum(1 for x in value if x is None)
            if holes == len(value):
                value = None
            elif holes != 0:
                raise BadArgumentUsage(
                    f"Argument {self.dest!r} takes {self.nargs} values."
                )
        if self.nargs == -1 and self.obj.envvar is not None and value == ():
            value = None
        state.opts[self.dest] = value
        state.order.append(self.obj)


class _Parser:
    def __init__(self, ctx: Context | None = None) -> None:
        self.ctx = ctx
        self.allow_interspersed_args = True
        self.ignore_unknown_options = False
        if ctx is not None:
            if ctx.allow_interspersed_args is not None:
                self.allow_interspersed_args = ctx.allow_interspersed_args
            if ctx.ignore_unknown_options is not None:
                self.ignore_unknown_options = ctx.ignore_unknown_options
        self._short_opt: dict[str, _Option] = {}
        self._long_opt: dict[str, _Option] = {}
        self._opt_prefixes = {"-", "--"}
        self._args: list[_Argument] = []
        self._positional_given = 0

    def add_option(
        self,
        obj: CoreOption,
        opts: t.Sequence[str],
        dest: str | None,
        action: str | None = None,
        nargs: int = 1,
        const: t.Any = None,
        optional_value: bool = False,
    ) -> None:
        opts = [normalize_opt(opt, self.ctx) for opt in opts]
        option = _Option(
            obj, opts, dest, action=action, nargs=nargs, const=const,
            optional_value=optional_value,
        )
        self._opt_prefixes.update(option.prefixes)
        for o in option._short_opts:
            self._short_opt[o] = option
        for o in option._long_opts:
            self._long_opt[o] = option

    def add_argument(
        self, obj: CoreArgument, dest: str | None, nargs: int = 1
    ) -> None:
        self._args.append(_Argument(obj, dest, nargs=nargs))

    def parse_args(
        self, args: list[str]
    ) -> tuple[dict[str, t.Any], list[str], list[Parameter]]:
        state = _State(args)
        try:
            self._process_opts(state)
        except UsageError:
            if self.ctx is None or not self.ctx.resilient_parsing:
                raise
        # Number of positional tokens available for arguments, recorded before
        # they are distributed. Completion uses it to find the argument at the
        # cursor.
        self._positional_given = len(state.largs)
        try:
            self._process_positionals(state)
        except UsageError:
            if self.ctx is None or not self.ctx.resilient_parsing:
                raise
        return state.opts, state.largs, state.order

    # -- options ------------------------------------------------------------
    def _process_opts(self, state: _State) -> None:
        while state.rargs:
            arg = state.rargs.pop(0)
            if arg == "--":
                state.largs.extend(state.rargs)
                del state.rargs[:]
                return
            if arg[:1] in self._opt_prefixes and len(arg) > 1:
                self._process_opt_token(arg, state)
            elif self.allow_interspersed_args:
                state.largs.append(arg)
            else:
                state.largs.append(arg)
                state.largs.extend(state.rargs)
                del state.rargs[:]
                return

    def _process_opt_token(self, arg: str, state: _State) -> None:
        prefix = _get_prefix(arg, self._opt_prefixes)
        if prefix == "--" or (len(prefix) == 2):
            self._process_long(arg, state)
        elif prefix in self._opt_prefixes:
            self._process_short(arg, state)
        else:
            self._unknown(arg, state)

    def _process_long(self, arg: str, state: _State) -> None:
        value: str | None
        if "=" in arg:
            opt, _, value = arg.partition("=")
        else:
            opt, value = arg, None
        norm = normalize_opt(opt, self.ctx)
        option = self._long_opt.get(norm)

        if option is None:
            if self.ignore_unknown_options:
                state.largs.append(arg)
                return
            possibilities = _close(norm, self._long_opt)
            raise NoSuchOption(opt, possibilities=possibilities, ctx=self.ctx)

        if option.takes_value:
            self._consume_value(option, norm, value, state)
        else:
            if value is not None:
                raise BadOptionUsage(
                    norm, f"Option {norm!r} does not take a value."
                )
            option.process(None, state)

    def _process_short(self, arg: str, state: _State) -> None:
        prefix = arg[0]
        i = 1
        while i < len(arg):
            opt = f"{prefix}{arg[i]}"
            i += 1
            option = self._short_opt.get(normalize_opt(opt, self.ctx))
            if option is None:
                if self.ignore_unknown_options:
                    state.largs.append(arg)
                    return
                raise NoSuchOption(opt, ctx=self.ctx)
            if option.takes_value:
                inline = arg[i:] if i < len(arg) else None
                self._consume_value(option, opt, inline, state)
                return
            option.process(None, state)

    def _consume_value(
        self,
        option: _Option,
        opt: str,
        inline_value: str | None,
        state: _State,
    ) -> None:
        nargs = option.nargs
        if nargs == 1:
            if inline_value is not None:
                value: t.Any = inline_value
            elif option.optional_value:
                if state.rargs and state.rargs[0][:1] not in self._opt_prefixes:
                    value = state.rargs.pop(0)
                else:
                    value = FLAG_NEEDS_VALUE
            elif state.rargs:
                value = state.rargs.pop(0)
            else:
                raise BadOptionUsage(opt, f"Option {opt!r} requires an argument.")
        else:
            collected: list[str] = []
            if inline_value is not None:
                collected.append(inline_value)
            while len(collected) < nargs and state.rargs:
                collected.append(state.rargs.pop(0))
            if len(collected) != nargs:
                raise BadOptionUsage(
                    opt, f"Option {opt!r} requires {nargs} arguments."
                )
            value = tuple(collected)
        option.process(value, state)

    def _unknown(self, arg: str, state: _State) -> None:
        if self.ignore_unknown_options:
            state.largs.append(arg)
            return
        raise NoSuchOption(arg, ctx=self.ctx)

    # -- positionals --------------------------------------------------------
    def _process_positionals(self, state: _State) -> None:
        pargs, args = _distribute(self._args, state.largs)
        for arg_obj in self._args:
            arg_obj.process(pargs.pop(0), state)
        state.largs = args


def _get_prefix(arg: str, prefixes: set[str]) -> str:
    if arg[:2] in prefixes:
        return arg[:2]
    if arg[:1] in prefixes:
        return arg[:1]
    return arg[:1]


def _close(opt: str, options: dict[str, _Option]) -> list[str]:
    import difflib

    return difflib.get_close_matches(opt, list(options))


def _distribute(
    args_spec: list[_Argument], values: list[str]
) -> tuple[list[t.Any], list[str]]:
    """Split *values* across the argument specs according to their nargs."""
    values = list(values)
    results: list[t.Any] = []

    # how many fixed slots are needed after a variadic one
    spos: int | None = None
    for i, arg in enumerate(args_spec):
        if arg.nargs == -1:
            if spos is not None:
                raise TypeError("Cannot have two nargs < 0")
            spos = i

    if spos is None:
        # no variadic: assign left to right
        for arg in args_spec:
            if arg.nargs == 1:
                results.append(values.pop(0) if values else None)
            else:
                taken = values[: arg.nargs]
                del values[: arg.nargs]
                taken += [None] * (arg.nargs - len(taken))
                results.append(tuple(taken))
        return results, values

    # variadic present: fill before and after it
    before = args_spec[:spos]
    after = args_spec[spos + 1 :]
    for arg in before:
        if arg.nargs == 1:
            results.append(values.pop(0) if values else None)
        else:
            taken = values[: arg.nargs]
            del values[: arg.nargs]
            results.append(tuple(taken))
    # reserve for after
    reserve = sum(1 if a.nargs == 1 else a.nargs for a in after)
    var_count = max(len(values) - reserve, 0)
    results.append(tuple(values[:var_count]))
    del values[:var_count]
    for arg in after:
        if arg.nargs == 1:
            results.append(values.pop(0) if values else None)
        else:
            taken = values[: arg.nargs]
            del values[: arg.nargs]
            results.append(tuple(taken))
    return results, values
