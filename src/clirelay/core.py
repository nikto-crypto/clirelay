"""Commands, parameters, and the runtime context.

This module ties everything together: :class:`Parameter` (and its concrete
:class:`Option` / :class:`Argument`), :class:`Command` and :class:`Group`, and
the :class:`Context` that carries state while a command runs.
"""
from __future__ import annotations

import enum
import inspect
import typing as t
from contextlib import contextmanager, ExitStack
from functools import update_wrapper
from gettext import gettext as _

from . import types as _types
from ._parsing import _Parser, split_opt
from ._sentinel import FLAG_NEEDS_VALUE, UNSET
from .exceptions import (
    Abort,
    BadParameter,
    ClickException,
    Exit,
    MissingParameter,
    NoArgsIsHelpError,
    NoSuchCommand,
    UsageError,
)
from .formatting import HelpFormatter, join_options
from .globals import pop_context, push_context
from .termui import confirm, prompt as _prompt_fn
from .utils import echo, make_str

if t.TYPE_CHECKING:
    from .shell_completion import CompletionItem

V = t.TypeVar("V")
F = t.TypeVar("F", bound=t.Callable[..., t.Any])


class ParameterSource(enum.IntEnum):
    """Where the value of a parameter came from."""

    PROMPT = 1
    COMMANDLINE = 2
    ENVIRONMENT = 3
    DEFAULT_MAP = 4
    DEFAULT = 5


def batch(iterable: t.Iterable[V], batch_size: int) -> list[tuple[V, ...]]:
    return list(zip(*([iter(iterable)] * batch_size)))


@contextmanager
def augment_usage_errors(
    ctx: Context, param: Parameter | None = None
) -> t.Iterator[None]:
    try:
        yield
    except BadParameter as e:
        if e.ctx is None:
            e.ctx = ctx
        if param is not None and e.param is None:
            e.param = param
        raise
    except UsageError as e:
        if e.ctx is None:
            e.ctx = ctx
        raise


def iter_params_for_processing(
    invocation_order: t.Sequence[Parameter],
    declaration_order: t.Sequence[Parameter],
) -> list[Parameter]:
    """Order parameters so eager ones (and those seen on the command line) run first."""

    def sort_key(item: Parameter) -> tuple[bool, float]:
        try:
            idx: float = invocation_order.index(item)
        except ValueError:
            idx = float("inf")
        return (not item.is_eager, idx)

    return sorted(declaration_order, key=sort_key)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

class Context:
    """State shared while a command parses and runs."""

    formatter_class: type[HelpFormatter] = HelpFormatter

    def __init__(
        self,
        command: Command,
        parent: Context | None = None,
        info_name: str | None = None,
        obj: t.Any | None = None,
        auto_envvar_prefix: str | None = None,
        default_map: t.MutableMapping[str, t.Any] | None = None,
        terminal_width: int | None = None,
        max_content_width: int | None = None,
        resilient_parsing: bool = False,
        allow_extra_args: bool | None = None,
        allow_interspersed_args: bool | None = None,
        ignore_unknown_options: bool | None = None,
        help_option_names: list[str] | None = None,
        token_normalize_func: t.Callable[[str], str] | None = None,
        color: bool | None = None,
        show_default: bool | None = None,
    ) -> None:
        self.parent = parent
        self.command = command
        self.info_name = info_name
        self.params: dict[str, t.Any] = {}
        self.args: list[str] = []
        self._protected_args: list[str] = []
        self._opt_prefixes: set[str] = set(parent._opt_prefixes) if parent else set()

        if obj is None and parent is not None:
            obj = parent.obj
        self.obj: t.Any = obj
        self._meta: dict[str, t.Any] = parent.meta if parent else {}

        if default_map is None and info_name is not None and parent is not None and parent.default_map is not None:
            default_map = parent.default_map.get(info_name)
        self.default_map = default_map

        self.invoked_subcommand: str | None = None

        if terminal_width is None and parent is not None:
            terminal_width = parent.terminal_width
        self.terminal_width = terminal_width

        if max_content_width is None and parent is not None:
            max_content_width = parent.max_content_width
        self.max_content_width = max_content_width

        if allow_extra_args is None:
            allow_extra_args = command.allow_extra_args
        self.allow_extra_args = allow_extra_args

        if allow_interspersed_args is None:
            allow_interspersed_args = command.allow_interspersed_args
        self.allow_interspersed_args = allow_interspersed_args

        if ignore_unknown_options is None:
            ignore_unknown_options = command.ignore_unknown_options
        self.ignore_unknown_options = ignore_unknown_options

        if help_option_names is None:
            if parent is not None:
                help_option_names = parent.help_option_names
            else:
                help_option_names = ["--help"]
        self.help_option_names = help_option_names

        if token_normalize_func is None and parent is not None:
            token_normalize_func = parent.token_normalize_func
        self.token_normalize_func = token_normalize_func

        self.resilient_parsing = resilient_parsing

        if auto_envvar_prefix is None:
            if parent is not None and parent.auto_envvar_prefix is not None and info_name is not None:
                auto_envvar_prefix = f"{parent.auto_envvar_prefix}_{info_name.upper()}"
        else:
            auto_envvar_prefix = auto_envvar_prefix.upper()
        if auto_envvar_prefix is not None:
            auto_envvar_prefix = auto_envvar_prefix.replace("-", "_")
        self.auto_envvar_prefix = auto_envvar_prefix

        if color is None and parent is not None:
            color = parent.color
        self.color = color

        if show_default is None and parent is not None:
            show_default = parent.show_default
        self.show_default = show_default

        self._close_callbacks: list[t.Callable[[], t.Any]] = []
        self._depth = 0
        self._parameter_source: dict[str, ParameterSource] = {}
        self._exit_stack = ExitStack()

    # -- properties ---------------------------------------------------------
    @property
    def protected_args(self) -> list[str]:
        return self._protected_args

    @property
    def meta(self) -> dict[str, t.Any]:
        return self._meta

    @property
    def command_path(self) -> str:
        rv = ""
        if self.info_name is not None:
            rv = self.info_name
        if self.parent is not None:
            parent_command_path = [self.parent.command_path]
            for param in self.parent.command.get_params(self):
                parent_command_path.extend(param.get_usage_pieces(self))
            rv = f"{' '.join(parent_command_path)} {rv}"
        return rv.lstrip()

    # -- info / help --------------------------------------------------------
    def to_info_dict(self) -> dict[str, t.Any]:
        return {
            "command": self.command.to_info_dict(self),
            "info_name": self.info_name,
            "allow_extra_args": self.allow_extra_args,
            "allow_interspersed_args": self.allow_interspersed_args,
            "ignore_unknown_options": self.ignore_unknown_options,
            "auto_envvar_prefix": self.auto_envvar_prefix,
        }

    def make_formatter(self) -> HelpFormatter:
        return self.formatter_class(
            width=self.terminal_width, max_width=self.max_content_width
        )

    def get_usage(self) -> str:
        return self.command.get_usage(self)

    def get_help(self) -> str:
        return self.command.get_help(self)

    # -- lifecycle ----------------------------------------------------------
    def __enter__(self) -> Context:
        self._depth += 1
        push_context(self)
        return self

    def __exit__(self, exc_type: t.Any, exc_value: t.Any, tb: t.Any) -> None:
        self._depth -= 1
        if self._depth == 0:
            self.close()
        pop_context()

    @contextmanager
    def scope(self, cleanup: bool = True) -> t.Iterator[Context]:
        if not cleanup:
            self._depth += 1
        try:
            with self as rv:
                yield rv
        finally:
            if not cleanup:
                self._depth -= 1

    def call_on_close(self, f: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        return self._exit_stack.callback(f)

    def with_resource(self, context_manager: t.ContextManager[V]) -> V:
        return self._exit_stack.enter_context(context_manager)

    def close(self) -> None:
        self._exit_stack.close()
        self._exit_stack = ExitStack()

    # -- object lookup ------------------------------------------------------
    def find_root(self) -> Context:
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    def find_object(self, object_type: type[V]) -> V | None:
        node: Context | None = self
        while node is not None:
            if isinstance(node.obj, object_type):
                return node.obj
            node = node.parent
        return None

    def ensure_object(self, object_type: type[V]) -> V:
        rv = self.find_object(object_type)
        if rv is None:
            self.obj = rv = object_type()
        return rv

    # -- parameter sources --------------------------------------------------
    def set_parameter_source(self, name: str, source: ParameterSource) -> None:
        self._parameter_source[name] = source

    def get_parameter_source(self, name: str) -> ParameterSource | None:
        return self._parameter_source.get(name)

    def lookup_default(self, name: str, call: bool = True) -> t.Any | None:
        if self.default_map is not None:
            value = self.default_map.get(name)
            if call and callable(value):
                return value()
            return value
        return None

    # -- invocation ---------------------------------------------------------
    def fail(self, message: str) -> t.NoReturn:
        raise UsageError(message, self)

    def abort(self) -> t.NoReturn:
        raise Abort()

    def exit(self, code: int = 0) -> t.NoReturn:
        raise Exit(code)

    @t.overload
    def invoke(self, callback: Command, /, *args: t.Any, **kwargs: t.Any) -> t.Any: ...
    @t.overload
    def invoke(self, callback: t.Callable[..., V], /, *args: t.Any, **kwargs: t.Any) -> V: ...

    def invoke(self, callback: t.Any, /, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if isinstance(callback, Command):
            other_cmd = callback
            if other_cmd.callback is None:
                raise TypeError("The given command does not have a callback that can be invoked.")
            callback = t.cast("t.Callable[..., t.Any]", other_cmd.callback)
            ctx = _make_subinvoke_context(self, other_cmd, args, kwargs)
            with augment_usage_errors(self):
                with ctx:
                    return callback(*args, **ctx.params)
        with augment_usage_errors(self):
            return callback(*args, **kwargs)

    def forward(self, cmd: Command, /, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if not isinstance(cmd, Command):
            raise TypeError("Callback is not a command.")
        for param in self.params:
            if param not in kwargs:
                kwargs[param] = self.params[param]
        return self.invoke(cmd, *args, **kwargs)


def _make_subinvoke_context(
    parent: Context, cmd: Command, args: tuple[t.Any, ...], kwargs: dict[str, t.Any]
) -> Context:
    ctx = Context(cmd, info_name=cmd.name, parent=parent)
    for param in cmd.get_params(ctx):
        if param.name not in kwargs and param.expose_value:
            kwargs[param.name] = param.get_default(ctx) if param.name not in kwargs else kwargs[param.name]
    ctx.params = kwargs
    return ctx


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

class Parameter:
    """Base class for options and arguments."""

    param_type_name = "parameter"

    def __init__(
        self,
        param_decls: t.Sequence[str] | None = None,
        type: t.Any = None,
        required: bool = False,
        default: t.Any = UNSET,
        callback: t.Callable[[Context, Parameter, t.Any], t.Any] | None = None,
        nargs: int | None = None,
        multiple: bool = False,
        metavar: str | None = None,
        expose_value: bool = True,
        is_eager: bool = False,
        envvar: str | t.Sequence[str] | None = None,
        shell_complete: t.Callable[..., t.Any] | None = None,
        deprecated: bool | str = False,
    ) -> None:
        self.name, self.opts, self.secondary_opts = self._parse_decls(
            param_decls or (), expose_value
        )
        self.type = _types.convert_type(type, default if default is not UNSET else None)

        if nargs is None:
            if self.type.is_composite:
                nargs = self.type.arity
            else:
                nargs = 1
        self.required = required
        self.callback = callback
        self.nargs = nargs
        self.multiple = multiple
        self.expose_value = expose_value
        self.default = None if default is UNSET else default
        self._default_is_unset = default is UNSET
        self.is_eager = is_eager
        self.metavar = metavar
        self.envvar = envvar
        self._custom_shell_complete = shell_complete
        self.deprecated = deprecated

        if __debug__:
            if self.type.is_composite and nargs != self.type.arity:
                raise ValueError(
                    f"'nargs' must be {self.type.arity} (or None) for type {self.type!r}, "
                    f"but it was {nargs}."
                )

    def to_info_dict(self) -> dict[str, t.Any]:
        return {
            "name": self.name,
            "param_type_name": self.param_type_name,
            "opts": self.opts,
            "secondary_opts": self.secondary_opts,
            "type": self.type.to_info_dict(),
            "required": self.required,
            "nargs": self.nargs,
            "multiple": self.multiple,
            "default": self.default,
            "envvar": self.envvar,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"

    def _parse_decls(
        self, decls: t.Sequence[str], expose_value: bool
    ) -> tuple[str | None, list[str], list[str]]:
        raise NotImplementedError()

    @property
    def human_readable_name(self) -> str:
        return self.name.upper() if self.name else ""

    def make_metavar(self, ctx: Context) -> str:
        if self.metavar is not None:
            return self.metavar
        metavar = self.type.get_metavar(self, ctx)
        if metavar is None:
            metavar = self.type.name.upper()
        if self.nargs != 1:
            metavar += "..."
        return metavar

    def get_default(
        self, ctx: Context, call: bool = True
    ) -> t.Any | t.Callable[[], t.Any] | None:
        value = ctx.lookup_default(self.name, call=False)
        if value is None:
            value = self.default
        if call and callable(value):
            value = value()
        return value

    def add_to_parser(self, parser: _Parser, ctx: Context) -> None:
        raise NotImplementedError()

    def consume_value(
        self, ctx: Context, opts: t.Mapping[str, t.Any]
    ) -> tuple[t.Any, ParameterSource]:
        value = opts.get(self.name)
        source = ParameterSource.COMMANDLINE
        if value is None:
            value = self.value_from_envvar(ctx)
            source = ParameterSource.ENVIRONMENT
        if value is None:
            value = ctx.lookup_default(self.name)
            source = ParameterSource.DEFAULT_MAP
        if value is None:
            value = self.get_default(ctx)
            source = ParameterSource.DEFAULT
        return value, source

    def type_cast_value(self, ctx: Context, value: t.Any) -> t.Any:
        if value is None:
            return () if self.multiple or self.nargs == -1 else None

        def check(val: t.Any) -> t.Any:
            return self.type(val, self, ctx)

        if self.type.is_composite:
            if self.multiple:
                return tuple(check(v) for v in value)
            return check(value)

        if self.multiple:
            return tuple(check(v) for v in value)
        if self.nargs == -1:
            return tuple(check(v) for v in value)
        if self.nargs != 1:
            return tuple(check(v) for v in value)
        return check(value)

    def value_is_missing(self, value: t.Any) -> bool:
        if value is None:
            return True
        if (self.nargs != 1 or self.multiple) and value == ():
            return True
        return False

    def process_value(self, ctx: Context, value: t.Any) -> t.Any:
        value = self.type_cast_value(ctx, value)
        if self.required and self.value_is_missing(value):
            raise MissingParameter(ctx=ctx, param=self)
        if self.callback is not None:
            value = self.callback(ctx, self, value)
        return value

    def resolve_envvar_value(self, ctx: Context) -> str | None:
        if self.envvar is None:
            return None
        import os

        if isinstance(self.envvar, str):
            rv = os.environ.get(self.envvar)
            if rv:
                return rv
        else:
            for envvar in self.envvar:
                rv = os.environ.get(envvar)
                if rv:
                    return rv
        return None

    def value_from_envvar(self, ctx: Context) -> t.Any:
        rv = self.resolve_envvar_value(ctx)
        if rv is not None and (self.nargs != 1 or self.multiple):
            rv = self.type.split_envvar_value(rv)
        return rv

    def handle_parse_result(
        self, ctx: Context, opts: t.Mapping[str, t.Any], args: list[str]
    ) -> tuple[t.Any, list[str]]:
        with augment_usage_errors(ctx, param=self):
            value, source = self.consume_value(ctx, opts)
            if (
                self.deprecated
                and value is not None
                and source
                not in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP)
            ):
                extra = f": {self.deprecated}" if isinstance(self.deprecated, str) else ""
                import warnings

                warnings.warn(
                    f"The {self.param_type_name} {self.name!r} is deprecated{extra}.",
                    category=DeprecationWarning,
                    stacklevel=2,
                )
            ctx.set_parameter_source(self.name, source)
            try:
                value = self.process_value(ctx, value)
            except Exception:
                if not ctx.resilient_parsing:
                    raise
                value = None
        if self.expose_value:
            ctx.params[self.name] = value
        return value, args

    def get_help_record(self, ctx: Context) -> tuple[str, str] | None:
        raise NotImplementedError()

    def get_usage_pieces(self, ctx: Context) -> list[str]:
        return []

    def get_error_hint(self, ctx: Context | None) -> str:
        hint_list = self.opts or [self.human_readable_name]
        return " / ".join(f"'{x}'" for x in hint_list)

    def shell_complete(self, ctx: Context, incomplete: str) -> list[CompletionItem]:
        from .shell_completion import CompletionItem

        if self._custom_shell_complete is not None:
            results = self._custom_shell_complete(ctx, self, incomplete)
            if results and isinstance(results[0], str):
                return [CompletionItem(c) for c in results]
            return t.cast("list[CompletionItem]", results)
        return self.type.shell_complete(ctx, self, incomplete)


class Option(Parameter):
    param_type_name = "option"

    def __init__(
        self,
        param_decls: t.Sequence[str] | None = None,
        show_default: bool | str | None = None,
        prompt: bool | str = False,
        confirmation_prompt: bool | str = False,
        prompt_required: bool = True,
        hide_input: bool = False,
        is_flag: bool | None = None,
        flag_value: t.Any = UNSET,
        multiple: bool = False,
        count: bool = False,
        allow_from_autoenv: bool = True,
        type: t.Any = None,
        help: str | None = None,
        hidden: bool = False,
        show_choices: bool = True,
        show_envvar: bool = False,
        deprecated: bool | str = False,
        **attrs: t.Any,
    ) -> None:
        if help:
            help = inspect.cleandoc(help)

        default_is_missing = "default" not in attrs or attrs["default"] is UNSET

        self._flag_value_was_set = flag_value is not UNSET

        super().__init__(param_decls, type=type, multiple=multiple, **attrs)

        if prompt is True:
            prompt_text: str | None = self.name.replace("_", " ").capitalize() if self.name else None
        elif prompt is False:
            prompt_text = None
        else:
            prompt_text = prompt
        self.prompt = prompt_text
        self.confirmation_prompt = confirmation_prompt
        self.prompt_required = prompt_required
        self.hide_input = hide_input
        self.hidden = hidden

        # determine flag-ness
        if is_flag is None:
            if flag_value is not UNSET:
                is_flag = True
            elif self.secondary_opts:
                is_flag = True
            else:
                is_flag = bool(self.is_bool_flag_candidate) if False else False
            if not is_flag and self.secondary_opts:
                is_flag = True
        else:
            if is_flag is False and flag_value is not UNSET:
                pass

        self.default_from_decls = default_is_missing

        if is_flag and default_is_missing and not self.required:
            self.default = False if not self.secondary_opts else self.default

        if flag_value is UNSET:
            flag_value = not (self.default if isinstance(self.default, bool) else False)

        self.is_flag = bool(is_flag)
        self.is_bool_flag = is_flag and isinstance(flag_value, bool)
        self.flag_value = flag_value
        self.count = count

        if count:
            self.is_flag = False
            if type is None:
                self.type = _types.IntRange(min=0)
            if self._default_is_unset:
                self.default = 0
            self.multiple = False

        if is_flag and self._default_is_unset and not self.secondary_opts:
            self.default = False

        self.show_default = show_default
        self.show_choices = show_choices
        self.show_envvar = show_envvar
        self.allow_from_autoenv = allow_from_autoenv
        self.help = help
        self.deprecated = deprecated

        if deprecated and self.required:
            raise ValueError(
                f"The option {self.name!r} is deprecated and still required. "
                "A deprecated option cannot be required."
            )

    # decl parsing ----------------------------------------------------------
    def _parse_decls(
        self, decls: t.Sequence[str], expose_value: bool
    ) -> tuple[str | None, list[str], list[str]]:
        opts: list[str] = []
        secondary_opts: list[str] = []
        name: str | None = None
        possible_names: list[tuple[str, str]] = []

        for decl in decls:
            if decl.isidentifier():
                if name is not None:
                    raise TypeError(f"Name '{name}' defined twice")
                name = decl
                continue
            split_char = ";" if decl[:1] == "/" else "/"
            if split_char in decl:
                first, second = decl.split(split_char, 1)
                first = first.rstrip()
                if first:
                    prefix, norm = split_opt(first)
                    possible_names.append((prefix, norm))
                    opts.append(first)
                second = second.lstrip()
                if second:
                    secondary_opts.append(second.lstrip())
            else:
                prefix, norm = split_opt(decl)
                possible_names.append((prefix, norm))
                opts.append(decl)

        if name is None and possible_names:
            possible_names.sort(key=lambda x: -len(x[0]))
            name = possible_names[0][1].replace("-", "_").lower()
            if not name.isidentifier():
                name = None

        if name is None:
            if not expose_value:
                return None, opts, secondary_opts
            raise TypeError(
                f"Could not determine name for option with declarations {decls!r}"
            )

        return name, opts, secondary_opts

    def add_to_parser(self, parser: _Parser, ctx: Context) -> None:
        if self.count:
            parser.add_option(self, self.opts, self.name, action="count")
        elif self.is_flag and self.secondary_opts:
            parser.add_option(self, self.opts, self.name, action="store_const", const=True)
            parser.add_option(self, self.secondary_opts, self.name, action="store_const", const=False)
        elif self.is_flag:
            parser.add_option(self, self.opts, self.name, action="store_const", const=self.flag_value)
        else:
            action = "append" if self.multiple else "store"
            parser.add_option(self, self.opts, self.name, action=action, nargs=self.nargs)

    def consume_value(
        self, ctx: Context, opts: t.Mapping[str, t.Any]
    ) -> tuple[t.Any, ParameterSource]:
        value = opts.get(self.name)
        source = ParameterSource.COMMANDLINE
        if value is None:
            value = self.value_from_envvar(ctx)
            source = ParameterSource.ENVIRONMENT
        if value is None:
            value = ctx.lookup_default(self.name)
            source = ParameterSource.DEFAULT_MAP
        if value is None and self.prompt is not None and not ctx.resilient_parsing:
            value = self.prompt_for_value(ctx)
            source = ParameterSource.PROMPT
        if value is None:
            value = self.get_default(ctx)
            source = ParameterSource.DEFAULT
        return value, source

    def prompt_for_value(self, ctx: Context) -> t.Any:
        default = self.get_default(ctx)
        if self.is_bool_flag:
            return confirm(self.prompt, default)
        return _prompt_fn(
            self.prompt,
            default=default,
            type=self.type,
            hide_input=self.hide_input,
            show_choices=self.show_choices,
            confirmation_prompt=self.confirmation_prompt,
            value_proc=lambda x: self.process_value(ctx, x),
        )

    @property
    def flag_activation_value(self) -> t.Any:
        return self.flag_value

    def get_default(
        self, ctx: Context, call: bool = True
    ) -> t.Any | t.Callable[[], t.Any] | None:
        if self.is_flag and not self.secondary_opts:
            value = super().get_default(ctx, call=call)
            if value is None:
                return False
            return value
        return super().get_default(ctx, call=call)

    def make_metavar(self, ctx: Context) -> str:
        if self.metavar is not None:
            return self.metavar
        metavar = self.type.get_metavar(self, ctx)
        if metavar is None:
            metavar = self.type.name.upper()
        if self.nargs != 1:
            metavar += "..."
        return metavar

    def get_help_record(self, ctx: Context) -> tuple[str, str] | None:
        if self.hidden:
            return None

        if self.secondary_opts:
            first = f"{join_options(self.opts)[0]} / {join_options(self.secondary_opts)[0]}"
        else:
            first = join_options(self.opts)[0]

        if not self.is_flag and not self.count:
            metavar = self.make_metavar(ctx)
            first = f"{first} {metavar}"

        help_text = self.help or ""
        if self.deprecated:
            extra_dep = (
                f" (DEPRECATED: {self.deprecated})"
                if isinstance(self.deprecated, str)
                else " (DEPRECATED)"
            )
            help_text = f"{help_text}{extra_dep}"

        extra = self.get_help_extra(ctx)
        if extra:
            extra_str = "; ".join(extra)
            help_text = f"{help_text}  [{extra_str}]" if help_text else f"[{extra_str}]"

        return first, help_text

    def get_help_extra(self, ctx: Context) -> list[str]:
        extra: list[str] = []

        if self.show_envvar:
            envvar = self.envvar
            if envvar is None and self.allow_from_autoenv and ctx.auto_envvar_prefix is not None and self.name is not None:
                envvar = f"{ctx.auto_envvar_prefix}_{self.name.upper()}"
            if envvar is not None:
                if isinstance(envvar, str):
                    extra.append(f"env var: {envvar}")
                else:
                    extra.append(f"env var: {', '.join(envvar)}")

        default_string = self._get_default_string(ctx)
        if default_string:
            extra.append(f"default: {default_string}")

        if isinstance(self.type, _types._NumberRangeBase) and not self.count:
            if self.type.min is not None or self.type.max is not None:
                extra.append(self.type._describe_range())

        if self.required:
            extra.append("required")

        return extra

    def _get_default_string(self, ctx: Context) -> str:
        if isinstance(self.show_default, str):
            return f"({self.show_default})"

        if self.show_default is True:
            show = True
        elif self.show_default is False:
            show = False
        else:
            show = bool(ctx.show_default)

        if not show:
            return ""

        default_value = self.get_default(ctx, call=False)
        if default_value is None:
            return ""
        if callable(default_value):
            return "(dynamic)"
        if self.is_bool_flag and self.secondary_opts:
            opt = (self.opts if default_value else self.secondary_opts)[0]
            return split_opt(opt)[1]
        if self.is_bool_flag and not default_value:
            return ""
        if isinstance(default_value, (list, tuple)):
            return ", ".join(str(d) for d in default_value)
        return str(default_value)

    @property
    def is_bool_flag_candidate(self) -> bool:
        return bool(self.secondary_opts)


class Argument(Parameter):
    param_type_name = "argument"

    def __init__(
        self,
        param_decls: t.Sequence[str],
        required: bool | None = None,
        help: str | None = None,
        **attrs: t.Any,
    ) -> None:
        if required is None:
            if attrs.get("default") is not None and attrs.get("default") is not UNSET:
                required = False
            else:
                required = attrs.get("nargs", 1) > 0
        if "multiple" in attrs:
            raise TypeError("__init__() got an unexpected keyword argument 'multiple'")
        self.help = help
        super().__init__(param_decls, required=required, **attrs)
        if self.default is not None and self.nargs == -1:
            raise TypeError("'default' is not supported for nargs=-1.")

    @property
    def human_readable_name(self) -> str:
        if self.metavar is not None:
            return self.metavar
        return self.name.upper() if self.name else ""

    def make_metavar(self, ctx: Context) -> str:
        if self.metavar is not None:
            return self.metavar
        metavar = self.type.get_metavar(self, ctx)
        if metavar is None:
            metavar = self.name.upper() if self.name else ""
        if not self.required:
            metavar = f"[{metavar}]"
        if self.nargs != 1:
            metavar += "..."
        if self.deprecated:
            metavar = f"{metavar[:-3]}!]..." if self.nargs != 1 else self._deprecated_metavar(metavar)
        return metavar

    def _deprecated_metavar(self, metavar: str) -> str:
        if metavar.endswith("]"):
            return f"{metavar[:-1]}!]"
        return f"{metavar}!"

    def _parse_decls(
        self, decls: t.Sequence[str], expose_value: bool
    ) -> tuple[str | None, list[str], list[str]]:
        if not decls:
            if not expose_value:
                return None, [], []
            raise TypeError("Could not determine name for argument")
        if len(decls) == 1:
            name = arg = decls[0]
            name = name.replace("-", "_").lower()
        else:
            raise TypeError(
                f"Arguments take exactly one parameter declaration, got {len(decls)}: {decls}."
            )
        return name, [arg], []

    def add_to_parser(self, parser: _Parser, ctx: Context) -> None:
        parser.add_argument(self, self.name, nargs=self.nargs)

    def get_usage_pieces(self, ctx: Context) -> list[str]:
        return [self.make_metavar(ctx)]

    def get_error_hint(self, ctx: Context | None) -> str:
        return f"'{self.make_metavar(ctx)}'" if ctx else f"'{self.human_readable_name}'"

    def get_help_record(self, ctx: Context) -> tuple[str, str] | None:
        help_text = self.help or ""
        if self.deprecated:
            extra_dep = (
                f" (DEPRECATED: {self.deprecated})"
                if isinstance(self.deprecated, str)
                else " (DEPRECATED)"
            )
            help_text = f"{help_text}{extra_dep}".strip()
        if not help_text:
            return None
        return self.make_metavar(ctx), help_text


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

class Command:
    """A single command: options, arguments, and a callback to run."""

    context_class: type[Context] = Context
    allow_extra_args = False
    allow_interspersed_args = True
    ignore_unknown_options = False

    def __init__(
        self,
        name: str | None,
        context_settings: t.MutableMapping[str, t.Any] | None = None,
        callback: t.Callable[..., t.Any] | None = None,
        params: list[Parameter] | None = None,
        help: str | None = None,
        epilog: str | None = None,
        short_help: str | None = None,
        options_metavar: str | None = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool | str = False,
    ) -> None:
        self.name = name
        if context_settings is None:
            context_settings = {}
        self.context_settings = context_settings
        self.callback = callback
        self.params = params or []
        if help and "\f" in help:
            help = help.split("\f", 1)[0]
        self.help = inspect.cleandoc(help) if help else help
        self.epilog = epilog
        self.options_metavar = options_metavar
        self.short_help = short_help
        self.add_help_option = add_help_option
        self.no_args_is_help = no_args_is_help
        self.hidden = hidden
        self.deprecated = deprecated

    def to_info_dict(self, ctx: Context) -> dict[str, t.Any]:
        return {
            "name": self.name,
            "params": [p.to_info_dict() for p in self.get_params(ctx)],
            "help": self.help,
            "epilog": self.epilog,
            "short_help": self.short_help,
            "hidden": self.hidden,
            "deprecated": self.deprecated,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"

    # -- parameters ---------------------------------------------------------
    def get_params(self, ctx: Context) -> list[Parameter]:
        params = list(self.params)
        help_option = self.get_help_option(ctx)
        if help_option is not None:
            params = [*params, help_option]
        _check_params(params)
        return params

    def get_help_option_names(self, ctx: Context) -> list[str]:
        all_names = set(ctx.help_option_names)
        for param in self.params:
            all_names.difference_update(param.opts)
            all_names.difference_update(param.secondary_opts)
        return list(all_names)

    def get_help_option(self, ctx: Context) -> Option | None:
        help_options = self.get_help_option_names(ctx)
        if not help_options or not self.add_help_option:
            return None

        def show_help(ctx: Context, param: Parameter, value: bool) -> None:
            if value and not ctx.resilient_parsing:
                echo(ctx.get_help(), color=ctx.color)
                ctx.exit()

        return Option(
            sorted(help_options, key=lambda s: (len(split_opt(s)[0]), s)),
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=show_help,
            help=_("Show this message and exit."),
        )

    def make_parser(self, ctx: Context) -> _Parser:
        parser = _Parser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    # -- parsing ------------------------------------------------------------
    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        if not args and self.no_args_is_help and not ctx.resilient_parsing:
            raise NoArgsIsHelpError(ctx)

        parser = self.make_parser(ctx)
        opts, args, param_order = parser.parse_args(args=args)

        for param in iter_params_for_processing(param_order, self.get_params(ctx)):
            value, args = param.handle_parse_result(ctx, opts, args)

        if args and not ctx.allow_extra_args and not ctx.resilient_parsing:
            ctx.fail(
                _("Got unexpected extra argument{s} ({args})").format(
                    s="s" if len(args) != 1 else "",
                    args=" ".join(map(str, args)),
                )
            )

        ctx.args = args
        ctx._opt_prefixes.update(parser._opt_prefixes)
        return args

    # -- usage / help -------------------------------------------------------
    def get_usage(self, ctx: Context) -> str:
        formatter = ctx.make_formatter()
        self.format_usage(ctx, formatter)
        return formatter.getvalue().rstrip("\n")

    def collect_usage_pieces(self, ctx: Context) -> list[str]:
        rv = [self.options_metavar] if self.options_metavar else []
        for param in self.get_params(ctx):
            rv.extend(param.get_usage_pieces(ctx))
        return rv

    def format_usage(self, ctx: Context, formatter: HelpFormatter) -> None:
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(ctx.command_path, " ".join(pieces))

    def get_help(self, ctx: Context) -> str:
        formatter = ctx.make_formatter()
        self.format_help(ctx, formatter)
        return formatter.getvalue().rstrip("\n")

    def get_short_help_str(self, limit: int = 45) -> str:
        if self.short_help:
            text = inspect.cleandoc(self.short_help)
        elif self.help:
            text = _make_default_short_help(self.help, limit)
        else:
            text = ""
        if self.deprecated:
            dep = (
                f"(DEPRECATED: {self.deprecated})"
                if isinstance(self.deprecated, str)
                else "(DEPRECATED)"
            )
            text = f"{text} {dep}".strip()
        return text.strip()

    def format_help(self, ctx: Context, formatter: HelpFormatter) -> None:
        self.format_usage(ctx, formatter)
        self.format_help_text(ctx, formatter)
        self.format_options(ctx, formatter)
        self.format_epilog(ctx, formatter)

    def format_help_text(self, ctx: Context, formatter: HelpFormatter) -> None:
        text = self.help or ""
        if self.deprecated:
            dep = (
                f"(DEPRECATED: {self.deprecated})"
                if isinstance(self.deprecated, str)
                else "(DEPRECATED)"
            )
            text = f"{text}\n\n{dep}" if text else dep

        if text:
            formatter.write_paragraph()
            with formatter.indentation():
                formatter.write_text(text)

    def format_arguments(self, ctx: Context, formatter: HelpFormatter) -> None:
        rows = []
        for param in self.get_params(ctx):
            if param.param_type_name != "argument":
                continue
            rv = param.get_help_record(ctx)
            if rv is not None:
                rows.append(rv)
        if rows:
            with formatter.section(_("Positional arguments")):
                formatter.write_dl(rows)

    def format_options(self, ctx: Context, formatter: HelpFormatter) -> None:
        self.format_arguments(ctx, formatter)
        opts = []
        for param in self.get_params(ctx):
            if param.param_type_name != "option":
                continue
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)
        if opts:
            with formatter.section(_("Options")):
                formatter.write_dl(opts)

    def format_epilog(self, ctx: Context, formatter: HelpFormatter) -> None:
        if self.epilog:
            epilog = inspect.cleandoc(self.epilog)
            formatter.write_paragraph()
            with formatter.indentation():
                formatter.write_text(epilog)

    # -- invocation ---------------------------------------------------------
    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: Context | None = None,
        **extra: t.Any,
    ) -> Context:
        for key, value in self.context_settings.items():
            if key not in extra:
                extra[key] = value
        ctx = self.context_class(self, info_name=info_name, parent=parent, **extra)
        with ctx.scope(cleanup=False):
            self.parse_args(ctx, args)
        return ctx

    def invoke(self, ctx: Context) -> t.Any:
        _check_deprecated(self, ctx)
        if self.callback is not None:
            return ctx.invoke(self.callback, **ctx.params)

    def main(
        self,
        args: t.Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: t.Any,
    ) -> t.Any:
        import sys

        if args is None:
            args = sys.argv[1:]
        else:
            args = list(args)

        if prog_name is None:
            prog_name = _detect_prog_name()

        if complete_var is None:
            complete_var = f"_{prog_name}_COMPLETE".replace("-", "_").upper()

        from .shell_completion import _start_completion

        if _start_completion(self, {}, prog_name, complete_var):
            return

        try:
            try:
                with self.make_context(prog_name, list(args), **extra) as ctx:
                    rv = self.invoke(ctx)
                    if not standalone_mode:
                        return rv
                    ctx.exit()
            except (EOFError, KeyboardInterrupt) as e:
                echo(file=sys.stderr)
                raise Abort() from e
            except ClickException as e:
                if not standalone_mode:
                    raise
                e.show()
                sys.exit(e.exit_code)
        except OSError as e:
            import errno

            if e.errno == errno.EPIPE:
                sys.stdout = t.cast("t.IO[t.Any]", _DevNull())
                sys.stderr = t.cast("t.IO[t.Any]", _DevNull())
                sys.exit(1)
            raise
        except Exit as e:
            if standalone_mode:
                sys.exit(e.exit_code)
            return e.exit_code
        except Abort:
            if not standalone_mode:
                raise
            echo(_("Aborted!"), file=sys.stderr)
            sys.exit(1)

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return self.main(*args, **kwargs)

    def shell_complete(self, ctx: Context, incomplete: str) -> list[CompletionItem]:
        from .shell_completion import CompletionItem

        results: list[CompletionItem] = []
        if incomplete and not incomplete[0].isalnum():
            for param in self.get_params(ctx):
                if not isinstance(param, Option) or param.hidden:
                    continue
                results.extend(
                    CompletionItem(name, help=param.help)
                    for name in [*param.opts, *param.secondary_opts]
                    if name.startswith(incomplete)
                    and ctx.get_parameter_source(param.name)
                    is not ParameterSource.COMMANDLINE
                )
        return results


class Group(Command):
    """A command that dispatches to subcommands."""

    allow_extra_args = True
    allow_interspersed_args = False

    command_class: type[Command] | None = None
    group_class: type[Command] | type[type] | None = None

    def __init__(
        self,
        name: str | None = None,
        commands: t.MutableMapping[str, Command] | t.Sequence[Command] | None = None,
        invoke_without_command: bool = False,
        no_args_is_help: bool | None = None,
        subcommand_metavar: str | None = None,
        chain: bool = False,
        result_callback: t.Callable[..., t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        if no_args_is_help is None:
            no_args_is_help = not invoke_without_command
        super().__init__(name, no_args_is_help=no_args_is_help, **kwargs)

        if commands is None:
            commands = {}
        elif isinstance(commands, (list, tuple)):
            commands = {c.name: c for c in commands if c.name is not None}
        self.commands: dict[str, Command] = dict(commands)

        self.invoke_without_command = invoke_without_command
        if subcommand_metavar is None:
            if chain:
                subcommand_metavar = "COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]..."
            else:
                subcommand_metavar = "COMMAND [ARGS]..."
        self.subcommand_metavar = subcommand_metavar
        self.chain = chain
        self._result_callback = result_callback

        if self.chain:
            for param in self.params:
                if isinstance(param, Argument) and param.nargs == -1:
                    raise RuntimeError(
                        "A group in chain mode cannot have an optional argument with nargs=-1."
                    )

    def to_info_dict(self, ctx: Context) -> dict[str, t.Any]:
        info = super().to_info_dict(ctx)
        commands = {}
        for name in self.list_commands(ctx):
            command = self.get_command(ctx, name)
            if command is None:
                continue
            sub_ctx = Context(command, info_name=name, parent=ctx)
            commands[name] = command.to_info_dict(sub_ctx)
        info["commands"] = commands
        info["chain"] = self.chain
        return info

    def add_command(self, cmd: Command, name: str | None = None) -> None:
        name = name or cmd.name
        if name is None:
            raise TypeError("Command has no name.")
        self.commands[name] = cmd

    def command(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        from .decorators import command as command_decorator

        func: t.Callable[..., t.Any] | None = None
        if args and callable(args[0]):
            func = args[0]
            args = args[1:]
            if kwargs.get("cls") is None and self.command_class is not None:
                kwargs["cls"] = self.command_class

        def decorator(f: t.Callable[..., t.Any]) -> Command:
            cls = kwargs.pop("cls", None) or self.command_class
            cmd = command_decorator(*args, cls=cls, **kwargs)(f) if cls else command_decorator(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd

        if func is not None:
            return decorator(func)
        return decorator

    def group(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        from .decorators import group as group_decorator

        func: t.Callable[..., t.Any] | None = None
        if args and callable(args[0]):
            func = args[0]
            args = args[1:]

        if self.group_class is not None and kwargs.get("cls") is None:
            if self.group_class is type:
                kwargs["cls"] = type(self)
            else:
                kwargs["cls"] = self.group_class

        def decorator(f: t.Callable[..., t.Any]) -> Command:
            cmd = group_decorator(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd

        if func is not None:
            return decorator(func)
        return decorator

    def result_callback(self, replace: bool = False) -> t.Callable[[F], F]:
        def decorator(f: F) -> F:
            old_callback = self._result_callback
            if old_callback is None or replace:
                self._result_callback = f
                return f

            def function(value: t.Any, /, *args: t.Any, **kwargs: t.Any) -> t.Any:
                inner = old_callback(value, *args, **kwargs)
                return f(inner, *args, **kwargs)

            self._result_callback = rv = update_wrapper(function, f)
            return rv  # type: ignore[return-value]

        return decorator

    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:
        return self.commands.get(cmd_name)

    def list_commands(self, ctx: Context) -> list[str]:
        return sorted(self.commands)

    def collect_usage_pieces(self, ctx: Context) -> list[str]:
        rv = super().collect_usage_pieces(ctx)
        rv.append(self.subcommand_metavar)
        return rv

    def format_options(self, ctx: Context, formatter: HelpFormatter) -> None:
        super().format_options(ctx, formatter)
        self.format_commands(ctx, formatter)

    def format_commands(self, ctx: Context, formatter: HelpFormatter) -> None:
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            commands.append((subcommand, cmd))
        if not commands:
            return
        limit = formatter.width - 6 - max(len(c[0]) for c in commands)
        rows = []
        for subcommand, cmd in commands:
            help_str = cmd.get_short_help_str(limit)
            rows.append((subcommand, help_str))
        if rows:
            with formatter.section(_("Commands")):
                formatter.write_dl(rows)

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        if not args and self.no_args_is_help and not ctx.resilient_parsing:
            raise NoArgsIsHelpError(ctx)

        rest = super(Group, self).parse_args(ctx, args)

        if self.chain:
            ctx._protected_args = rest
            ctx.args = []
        elif rest:
            ctx._protected_args, ctx.args = rest[:1], rest[1:]

        return ctx.args

    def invoke(self, ctx: Context) -> t.Any:
        _check_deprecated(self, ctx)

        def _process_result(value: t.Any) -> t.Any:
            if self._result_callback is not None:
                value = ctx.invoke(self._result_callback, value, **ctx.params)
            return value

        if not ctx._protected_args:
            if self.invoke_without_command:
                if not self.chain:
                    with ctx:
                        super().invoke(ctx)
                        return _process_result([])
                with ctx:
                    super().invoke(ctx)
                    return _process_result([])
            raise NoArgsIsHelpError(ctx)

        args = [*ctx._protected_args, *ctx.args]
        ctx.args = []
        ctx._protected_args = []

        if not self.chain:
            with ctx:
                cmd_name, cmd, args = self.resolve_command(ctx, args)
                assert cmd is not None
                ctx.invoked_subcommand = cmd_name
                super().invoke(ctx)
                sub_ctx = cmd.make_context(cmd_name, args, parent=ctx)
                with sub_ctx:
                    return _process_result(sub_ctx.command.invoke(sub_ctx))

        with ctx:
            ctx.invoked_subcommand = "*" if args else None
            super().invoke(ctx)
            contexts = []
            while args:
                cmd_name, cmd, args = self.resolve_command(ctx, args)
                assert cmd is not None
                sub_ctx = cmd.make_context(
                    cmd_name,
                    args,
                    parent=ctx,
                    allow_extra_args=True,
                    allow_interspersed_args=False,
                )
                contexts.append(sub_ctx)
                args, sub_ctx.args = sub_ctx.args, []
            rv = []
            for sub_ctx in contexts:
                with sub_ctx:
                    rv.append(sub_ctx.command.invoke(sub_ctx))
            return _process_result(rv)

    def resolve_command(
        self, ctx: Context, args: list[str]
    ) -> tuple[str | None, Command | None, list[str]]:
        cmd_name = make_str(args[0])
        original_cmd_name = cmd_name
        cmd = self.get_command(ctx, cmd_name)

        if cmd is None and ctx.token_normalize_func is not None:
            cmd_name = ctx.token_normalize_func(cmd_name)
            cmd = self.get_command(ctx, cmd_name)

        if cmd is None and not ctx.resilient_parsing:
            if split_opt(cmd_name)[0]:
                self.parse_args(ctx, ctx.args)
            possibilities = [
                name
                for name in self.list_commands(ctx)
            ]
            import difflib

            matches = difflib.get_close_matches(original_cmd_name, possibilities)
            raise NoSuchCommand(original_cmd_name, possibilities=matches, ctx=ctx)

        return cmd_name if cmd else None, cmd, args[1:]


class CommandCollection(Group):
    """A group backed by several source groups."""

    def __init__(
        self,
        name: str | None = None,
        sources: list[Group] | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.sources: list[Group] = sources or []

    def add_source(self, group: Group) -> None:
        self.sources.append(group)

    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:
        for source in self.sources:
            rv = source.get_command(ctx, cmd_name)
            if rv is not None:
                if self.chain:
                    _check_multicommand(self, cmd_name, rv)
                return rv
        return None

    def list_commands(self, ctx: Context) -> list[str]:
        rv: set[str] = set()
        for source in self.sources:
            rv.update(source.list_commands(ctx))
        return sorted(rv)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _check_params(params: t.Sequence[Parameter]) -> None:
    import warnings

    seen: dict[str, Parameter] = {}
    arg_names: set[str] = set()
    opt_names: set[str] = set()
    for param in params:
        if param.name is None:
            continue
        for opt in [*param.opts, *param.secondary_opts]:
            if opt in seen:
                warnings.warn(
                    f"The parameter {opt} is used more than once. "
                    "Remove its duplicate as parameters should be unique.",
                    stacklevel=3,
                )
            seen[opt] = param
        if param.param_type_name == "argument":
            arg_names.add(param.name)
        else:
            opt_names.add(param.name)
    clash = arg_names & opt_names
    for name in clash:
        warnings.warn(
            f"The name {name!r} is used by an argument and another parameter. "
            "This will be an error in a future version.",
            stacklevel=3,
        )


def _check_deprecated(cmd: Command, ctx: Context) -> None:
    if cmd.deprecated and not ctx.resilient_parsing:
        import warnings

        extra = f": {cmd.deprecated}" if isinstance(cmd.deprecated, str) else ""
        warnings.warn(
            f"The command {cmd.name!r} is deprecated{extra}.",
            category=DeprecationWarning,
            stacklevel=2,
        )


def _check_multicommand(
    base_command: Group, cmd_name: str, cmd: Command, register: bool = False
) -> None:
    if not base_command.chain or not isinstance(cmd, Group):
        return
    raise RuntimeError("chained group cannot contain other groups")


def _make_default_short_help(help: str, max_length: int = 45) -> str:
    line_ending = help.find("\n\n")
    paragraph = help[:line_ending] if line_ending != -1 else help
    words = paragraph.split()
    if not words:
        return ""
    total_length = 0
    last_index = len(words) - 1
    result: list[str] = []
    done = False
    for i, word in enumerate(words):
        total_length += len(word) + (1 if i > 0 else 0)
        if total_length > max_length:
            result.append("...")
            done = True
        else:
            result.append(word)
            if i != last_index and word.endswith("."):
                done = True
        if done:
            break
    return " ".join(result)


def _detect_prog_name() -> str:
    import sys
    import os

    name = sys.argv and sys.argv[0]
    if not name:
        return "clirelay"
    main = sys.modules.get("__main__")
    package = getattr(main, "__package__", None)
    if package not in (None, ""):
        py = os.path.basename(getattr(sys, "executable", "python") or "python")
        return f"{py} -m {package}"
    return os.path.basename(name)


class _DevNull:
    def write(self, *a: t.Any) -> None:
        pass

    def flush(self) -> None:
        pass
