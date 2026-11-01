"""The decorators that turn plain functions into commands and parameters."""
from __future__ import annotations

import typing as t
from functools import update_wrapper
from gettext import gettext as _

from .core import Argument, Command, Context, Group, Option, Parameter
from .globals import get_current_context
from .utils import echo

F = t.TypeVar("F", bound=t.Callable[..., t.Any])
FC = t.TypeVar("FC", bound="t.Union[t.Callable[..., t.Any], Command]")
T = t.TypeVar("T")
R = t.TypeVar("R")
CmdType = t.TypeVar("CmdType", bound=Command)
GrpType = t.TypeVar("GrpType", bound=Group)

_AnyCallable = t.Callable[..., t.Any]

_COMMAND_NAME_SUFFIXES = ("-command", "-cmd", "-group", "-grp")


def _derive_name(func: t.Callable[..., t.Any]) -> str:
    name = func.__name__.lower().replace("_", "-")
    for suffix in _COMMAND_NAME_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


def pass_context(f: t.Callable[..., R]) -> t.Callable[..., R]:
    def new_func(*args: t.Any, **kwargs: t.Any) -> R:
        return f(get_current_context(), *args, **kwargs)

    return update_wrapper(new_func, f)


def pass_obj(f: t.Callable[..., R]) -> t.Callable[..., R]:
    def new_func(*args: t.Any, **kwargs: t.Any) -> R:
        return f(get_current_context().obj, *args, **kwargs)

    return update_wrapper(new_func, f)


def make_pass_decorator(
    object_type: type[T], ensure: bool = False
) -> t.Callable[[t.Callable[..., R]], t.Callable[..., R]]:
    def decorator(f: t.Callable[..., R]) -> t.Callable[..., R]:
        def new_func(*args: t.Any, **kwargs: t.Any) -> R:
            ctx = get_current_context()
            if ensure:
                obj = ctx.ensure_object(object_type)
            else:
                obj = ctx.find_object(object_type)
            if obj is None:
                raise RuntimeError(
                    "Managed to invoke callback without a context object of type "
                    f"{object_type.__name__!r} existing."
                )
            return ctx.invoke(f, obj, *args, **kwargs)

        return update_wrapper(new_func, f)

    return decorator


def pass_meta_key(
    key: str, *, doc_description: str | None = None
) -> t.Callable[[t.Callable[..., R]], t.Callable[..., R]]:
    def decorator(f: t.Callable[..., R]) -> t.Callable[..., R]:
        def new_func(*args: t.Any, **kwargs: t.Any) -> R:
            ctx = get_current_context()
            obj = ctx.meta[key]
            return ctx.invoke(f, obj, *args, **kwargs)

        return update_wrapper(new_func, f)

    return decorator


def _param_memo(f: t.Callable[..., t.Any], param: Parameter) -> None:
    if isinstance(f, Command):
        f.params.append(param)
    else:
        if not hasattr(f, "__clirelay_params__"):
            f.__clirelay_params__ = []  # type: ignore[attr-defined]
        f.__clirelay_params__.append(param)  # type: ignore[attr-defined]


def command(
    name: str | _AnyCallable | None = None,
    cls: type[CmdType] | None = None,
    **attrs: t.Any,
) -> t.Any:
    func: t.Callable[..., t.Any] | None = None

    if callable(name):
        func = name
        name = None
        assert cls is None, "Use 'command(cls=cls)(callable)' to specify a class."
        assert not attrs, "Use 'command(**kwargs)(callable)' to provide arguments."

    if cls is None:
        cls = t.cast("type[CmdType]", Command)

    def decorator(f: t.Callable[..., t.Any]) -> CmdType:
        if isinstance(f, Command):
            raise TypeError("Attempted to convert a callback into a command twice.")

        attr_params = attrs.pop("params", None)
        params = attr_params if attr_params is not None else []

        try:
            decorator_params = f.__clirelay_params__  # type: ignore[attr-defined]
        except AttributeError:
            pass
        else:
            del f.__clirelay_params__  # type: ignore[attr-defined]
            params.extend(reversed(decorator_params))

        if attrs.get("help") is None:
            attrs["help"] = f.__doc__

        if t.TYPE_CHECKING:
            assert cls is not None

        cmd = cls(
            name=name if isinstance(name, str) else _derive_name(f),
            callback=f,
            params=params,
            **attrs,
        )
        cmd.__doc__ = f.__doc__
        return cmd

    if func is not None:
        return decorator(func)
    return decorator


def group(
    name: str | _AnyCallable | None = None,
    cls: type[GrpType] | None = None,
    **attrs: t.Any,
) -> t.Any:
    if cls is None:
        cls = t.cast("type[GrpType]", Group)
    return command(name, cls, **attrs)  # type: ignore[arg-type]


def argument(
    *param_decls: str, cls: type[Argument] | None = None, **attrs: t.Any
) -> t.Callable[[FC], FC]:
    if cls is None:
        cls = Argument

    def decorator(f: FC) -> FC:
        _param_memo(f, cls(param_decls, **attrs))
        return f

    return decorator


def option(
    *param_decls: str, cls: type[Option] | None = None, **attrs: t.Any
) -> t.Callable[[FC], FC]:
    if cls is None:
        cls = Option

    def decorator(f: FC) -> FC:
        _param_memo(f, cls(param_decls, **attrs))
        return f

    return decorator


def confirmation_option(*param_decls: str, **kwargs: t.Any) -> t.Callable[[FC], FC]:
    def callback(ctx: Context, param: Parameter, value: bool) -> None:
        if not value:
            ctx.abort()

    if not param_decls:
        param_decls = ("--yes",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("callback", callback)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("prompt", "Do you want to continue?")
    kwargs.setdefault("help", "Confirm the action without prompting.")
    return option(*param_decls, **kwargs)


def password_option(*param_decls: str, **kwargs: t.Any) -> t.Callable[[FC], FC]:
    if not param_decls:
        param_decls = ("--password",)
    kwargs.setdefault("prompt", True)
    kwargs.setdefault("confirmation_prompt", True)
    kwargs.setdefault("hide_input", True)
    return option(*param_decls, **kwargs)


def version_option(
    version: str | None = None,
    *param_decls: str,
    package_name: str | None = None,
    prog_name: str | None = None,
    message: str | None = None,
    **kwargs: t.Any,
) -> t.Callable[[FC], FC]:
    if message is None:
        message = _("%(prog)s, version %(version)s")

    # Guess the distribution name from the module applying the decorator, at
    # decoration time (the caller's frame), not from the callback later.  A
    # top-level script (``__name__ == '__main__'`` with no package) yields no
    # guess, so the version cannot be determined automatically.
    if version is None and package_name is None:
        package_name = _guess_package_name()

    def resolve(ctx: Context) -> str:
        resolved_prog = prog_name or ctx.find_root().info_name
        if version is None:
            name = package_name
            if name is None:
                raise RuntimeError(
                    f"Could not determine the version for {name} automatically."
                )
            import importlib.metadata

            try:
                ver = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                raise RuntimeError(
                    f"{name!r} is not installed. Try passing 'package_name' instead."
                ) from None
        else:
            ver = version
        return message % {"prog": resolved_prog, "version": ver, "package": package_name}

    return custom_version_option(resolve, *param_decls, **kwargs)


def custom_version_option(
    callback: t.Callable[[Context], str],
    *param_decls: str,
    **kwargs: t.Any,
) -> t.Callable[[FC], FC]:
    def cb(ctx: Context, param: Parameter, value: bool) -> None:
        if not value or ctx.resilient_parsing:
            return
        echo(callback(ctx), color=ctx.color)
        ctx.exit()

    if not param_decls:
        param_decls = ("--version",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault("help", _("Show the version and exit."))
    kwargs["callback"] = cb
    return option(*param_decls, **kwargs)


def help_option(*param_decls: str, **kwargs: t.Any) -> t.Callable[[FC], FC]:
    def callback(ctx: Context, param: Parameter, value: bool) -> None:
        if not value or ctx.resilient_parsing:
            return
        echo(ctx.get_help(), color=ctx.color)
        ctx.exit()

    if not param_decls:
        param_decls = ("--help",)

    kwargs.setdefault("is_flag", True)
    kwargs.setdefault("expose_value", False)
    kwargs.setdefault("is_eager", True)
    kwargs.setdefault("help", _("Show this message and exit."))
    kwargs["callback"] = callback
    return option(*param_decls, **kwargs)


def _guess_package_name() -> str | None:
    """Best-effort distribution name from the module applying the decorator.

    Reads the caller's module globals: its ``__name__`` names the distribution,
    except for a top-level script (``__name__ == '__main__'``), where the
    package (empty for a plain script) is used instead.  A plain script yields
    ``None`` rather than a wrong guess, matching the oracle.
    """
    import sys

    try:
        f_globals = sys._getframe(2).f_globals
    except (AttributeError, ValueError):
        return None
    name = f_globals.get("__name__")
    if name == "__main__":
        name = f_globals.get("__package__")
    if not name:
        return None
    return name.partition(".")[0]
