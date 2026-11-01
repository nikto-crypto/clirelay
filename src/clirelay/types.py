"""Parameter types: how raw command-line strings become Python values.

Each type knows how to :meth:`convert` an input, how to describe itself in a
usage line (:meth:`get_metavar`), and how to serialize itself
(:meth:`to_info_dict`).  A failed conversion raises through :meth:`fail`.
"""
from __future__ import annotations

import datetime as _dt
import enum as _enum
import os
import stat
import sys
import typing as t
import uuid as _uuid

from .exceptions import BadParameter
from .utils import format_filename

if t.TYPE_CHECKING:
    from .core import Context, Parameter
    from .shell_completion import CompletionItem

_FS_ENCODING = sys.getfilesystemencoding() or "utf-8"


def _info_param_type(cls: type) -> str:
    name = cls.__name__
    for suffix in ("ParameterType", "ParamType"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


class ParamType:
    """Base class for all parameter types."""

    is_composite: t.ClassVar[bool] = False
    arity: t.ClassVar[int] = 1
    name: str
    envvar_list_splitter: t.ClassVar[str | None] = None

    def __class_getitem__(cls, item: t.Any) -> type:
        return cls

    def to_info_dict(self) -> dict[str, t.Any]:
        param_type = _info_param_type(type(self))
        name = getattr(self, "name", None)
        if name is None:
            name = type(self).__name__
        return {"param_type": param_type, "name": name}

    def __call__(
        self,
        value: t.Any,
        param: Parameter | None = None,
        ctx: Context | None = None,
    ) -> t.Any:
        if value is not None:
            return self.convert(value, param, ctx)
        return value

    def get_metavar(self, param: Parameter, ctx: Context) -> str | None:
        return None

    def get_missing_message(
        self, param: Parameter, ctx: Context | None
    ) -> str | None:
        return None

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        return value

    def split_envvar_value(self, rv: str) -> t.Sequence[str]:
        return (rv or "").split(self.envvar_list_splitter)

    def fail(
        self,
        message: str,
        param: Parameter | None = None,
        ctx: Context | None = None,
    ) -> t.NoReturn:
        raise BadParameter(message, ctx=ctx, param=param)

    def shell_complete(
        self, ctx: Context, param: Parameter, incomplete: str
    ) -> list[CompletionItem]:
        return []


class CompositeParamType(ParamType):
    is_composite = True

    @property
    def arity(self) -> int:  # type: ignore[override]
        raise NotImplementedError()


class FuncParamType(ParamType):
    def __init__(self, func: t.Callable[[t.Any], t.Any]) -> None:
        self.name = func.__name__
        self.func = func

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {"func": self.func}
        info.update(super().to_info_dict())
        return info

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        try:
            return self.func(value)
        except ValueError:
            try:
                value = str(value)
            except UnicodeError:
                value = value.decode("utf-8", "replace")
            self.fail(value, param, ctx)


class UnprocessedParamType(ParamType):
    name = "text"

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        return value

    def __repr__(self) -> str:
        return "UNPROCESSED"


class StringParamType(ParamType):
    name = "text"

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        if isinstance(value, bytes):
            try:
                return value.decode(_FS_ENCODING)
            except UnicodeError:
                return value.decode("utf-8", "replace")
        return str(value)

    def __repr__(self) -> str:
        return "STRING"


class _NumberParamTypeBase(ParamType):
    _number_class: t.ClassVar[type]

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        try:
            return self._number_class(value)
        except ValueError:
            self.fail(f"{value!r} is not a valid {self.name}.", param, ctx)


class IntParamType(_NumberParamTypeBase):
    name = "integer"
    _number_class = int

    def __repr__(self) -> str:
        return "INT"


class FloatParamType(_NumberParamTypeBase):
    name = "float"
    _number_class = float

    def __repr__(self) -> str:
        return "FLOAT"


class _NumberRangeBase(_NumberParamTypeBase):
    def __init__(
        self,
        min: t.Any = None,
        max: t.Any = None,
        min_open: bool = False,
        max_open: bool = False,
        clamp: bool = False,
    ) -> None:
        self.min = min
        self.max = max
        self.min_open = min_open
        self.max_open = max_open
        self.clamp = clamp

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {
            "min": self.min,
            "max": self.max,
            "min_open": self.min_open,
            "max_open": self.max_open,
            "clamp": self.clamp,
        }
        info.update(super().to_info_dict())
        return info

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        import operator

        rv = super().convert(value, param, ctx)

        if self.clamp:
            return self._clamp(rv)

        lt_min = (
            self.min is not None
            and (operator.le if self.min_open else operator.lt)(rv, self.min)
        )
        gt_max = (
            self.max is not None
            and (operator.ge if self.max_open else operator.gt)(rv, self.max)
        )
        if lt_min or gt_max:
            self.fail(
                f"{rv} is not in the range {self._describe_range()}.",
                param,
                ctx,
            )
        return rv

    def _clamp(self, value: t.Any) -> t.Any:
        raise NotImplementedError()

    def _describe_range(self) -> str:
        if self.min is not None and self.max is not None:
            op_min = "<" if self.min_open else "<="
            op_max = "<" if self.max_open else "<="
            return f"{self.min}{op_min}x{op_max}{self.max}"
        if self.min is not None:
            op = ">" if self.min_open else ">="
            return f"x{op}{self.min}"
        if self.max is not None:
            op = "<" if self.max_open else "<="
            return f"x{op}{self.max}"
        return "x"

    def __repr__(self) -> str:
        clamp = " clamped" if self.clamp else ""
        return f"<{type(self).__name__} {self._describe_range()}{clamp}>"


class IntRange(_NumberRangeBase, IntParamType):
    name = "integer range"

    def _clamp(self, value: t.Any) -> t.Any:
        if self.min is not None:
            min_adj = self.min + 1 if self.min_open else self.min
            if value < min_adj:
                return min_adj
        if self.max is not None:
            max_adj = self.max - 1 if self.max_open else self.max
            if value > max_adj:
                return max_adj
        return value


class FloatRange(_NumberRangeBase, FloatParamType):
    name = "float range"

    def __init__(
        self,
        min: float | None = None,
        max: float | None = None,
        min_open: bool = False,
        max_open: bool = False,
        clamp: bool = False,
    ) -> None:
        super().__init__(min, max, min_open, max_open, clamp)
        if clamp and (min_open or max_open):
            raise TypeError("Clamping is not supported for open bounds.")

    def _clamp(self, value: t.Any) -> t.Any:
        if self.min is not None and value < self.min:
            return self.min
        if self.max is not None and value > self.max:
            return self.max
        return value


class BoolParamType(ParamType):
    name = "boolean"

    bool_states: t.ClassVar[dict[str, bool]] = {
        "1": True, "0": False,
        "yes": True, "no": False,
        "true": True, "false": False,
        "on": True, "off": False,
        "t": True, "f": False,
        "y": True, "n": False,
        "": False,
    }

    @staticmethod
    def str_to_bool(value: str | bool) -> bool | None:
        if isinstance(value, bool):
            return value
        return BoolParamType.bool_states.get(str(value).strip().lower())

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        rv = self.str_to_bool(value)
        if rv is None:
            recognized = ", ".join(sorted(self.bool_states))
            self.fail(
                f"{value!r} is not a valid boolean. Recognized values: {recognized}",
                param,
                ctx,
            )
        return rv

    def __repr__(self) -> str:
        return "BOOL"


class UUIDParameterType(ParamType):
    name = "uuid"

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        if isinstance(value, _uuid.UUID):
            return value
        value = value.strip() if isinstance(value, str) else value
        try:
            return _uuid.UUID(value)
        except ValueError:
            self.fail(f"{value!r} is not a valid UUID.", param, ctx)

    def __repr__(self) -> str:
        return "UUID"


class Choice(ParamType):
    name = "choice"

    def __init__(
        self, choices: t.Iterable[t.Any], case_sensitive: bool = True
    ) -> None:
        self.choices = choices
        self.case_sensitive = case_sensitive

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {
            "choices": self._choice_values(),
            "case_sensitive": self.case_sensitive,
        }
        info.update(super().to_info_dict())
        return info

    def _is_enum(self) -> bool:
        return isinstance(self.choices, type) and issubclass(self.choices, _enum.Enum)

    def _choice_values(self) -> tuple[t.Any, ...]:
        if self._is_enum():
            return tuple(self.choices)
        return tuple(self.choices)

    def _display_choices(self, ctx: Context | None = None) -> list[str]:
        return [self.normalize_choice(c, ctx) for c in self._choice_values()]

    def normalize_choice(self, choice: t.Any, ctx: Context | None) -> str:
        if isinstance(choice, _enum.Enum):
            text = choice.name
        else:
            text = str(choice)
        if ctx is not None and ctx.token_normalize_func is not None:
            text = ctx.token_normalize_func(text)
        if not self.case_sensitive:
            text = text.casefold()
        return text

    def get_metavar(self, param: Parameter, ctx: Context) -> str | None:
        choices_str = "|".join(self._display_choices(ctx))
        if param.required and param.param_type_name == "argument":
            return f"{{{choices_str}}}"
        return f"[{choices_str}]"

    def get_missing_message(
        self, param: Parameter, ctx: Context | None
    ) -> str | None:
        formatted = ",\n\t".join(self._display_choices(ctx))
        return f"Choose from:\n\t{formatted}"

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        normalized_value = self.normalize_choice(value, ctx)
        mapping = {
            self.normalize_choice(choice, ctx): choice
            for choice in self._choice_values()
        }
        if normalized_value in mapping:
            return mapping[normalized_value]
        self.fail(self.get_invalid_choice_message(value, ctx), param, ctx)

    def get_invalid_choice_message(self, value: t.Any, ctx: Context | None) -> str:
        choices = self._display_choices(ctx)
        if len(choices) == 1:
            return f"{value!r} is not {choices[0]!r}."
        joined = ", ".join(repr(c) for c in choices)
        return f"{value!r} is not one of {joined}."

    def shell_complete(
        self, ctx: Context, param: Parameter, incomplete: str
    ) -> list[CompletionItem]:
        from .shell_completion import CompletionItem

        results = []
        incomplete_norm = incomplete if self.case_sensitive else incomplete.casefold()
        for choice in self._display_choices(ctx):
            cmp = choice if self.case_sensitive else choice.casefold()
            if cmp.startswith(incomplete_norm):
                results.append(CompletionItem(choice))
        return results

    def __repr__(self) -> str:
        return f"Choice({list(self._choice_values())})"


class DateTime(ParamType):
    name = "datetime"

    def __init__(self, formats: t.Sequence[str] | None = None) -> None:
        self.formats = list(
            formats or ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]
        )

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {"formats": self.formats}
        info.update(super().to_info_dict())
        return info

    def get_metavar(self, param: Parameter, ctx: Context) -> str:
        return f"[{'|'.join(self.formats)}]"

    def _try(self, value: str, fmt: str) -> _dt.datetime | None:
        try:
            return _dt.datetime.strptime(value, fmt)
        except ValueError:
            return None

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        if isinstance(value, _dt.datetime):
            return value
        for fmt in self.formats:
            converted = self._try(value, fmt)
            if converted is not None:
                return converted
        formats_str = ", ".join(repr(f) for f in self.formats)
        if len(self.formats) == 1:
            self.fail(
                f"{value!r} does not match the format {formats_str}.", param, ctx
            )
        self.fail(
            f"{value!r} does not match the formats {formats_str}.", param, ctx
        )

    def __repr__(self) -> str:
        return "DateTime"


class Tuple(CompositeParamType):
    def __init__(
        self, types: t.Sequence[type[t.Any] | ParamType]
    ) -> None:
        self.types = [convert_type(ty) for ty in types]

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {
            "types": [ty.to_info_dict() for ty in self.types]
        }
        info.update(super().to_info_dict())
        return info

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"<{' '.join(ty.name for ty in self.types)}>"

    @property
    def arity(self) -> int:  # type: ignore[override]
        return len(self.types)

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        length = len(self.types)
        if len(value) != length:
            self.fail(
                f"{value!r} takes {length} values but {len(value)} "
                f"{'was' if len(value) == 1 else 'were'} given.",
                param,
                ctx,
            )
        return tuple(ty(x, param, ctx) for ty, x in zip(self.types, value))


class File(ParamType):
    name = "filename"
    envvar_list_splitter = os.path.pathsep

    def __init__(
        self,
        mode: str = "r",
        encoding: str | None = None,
        errors: str | None = "strict",
        lazy: bool | None = None,
        atomic: bool = False,
    ) -> None:
        self.mode = mode
        self.encoding = encoding
        self.errors = errors
        self.lazy = lazy
        self.atomic = atomic

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {"mode": self.mode, "encoding": self.encoding}
        info.update(super().to_info_dict())
        return info

    def shell_complete(
        self, ctx: Context, param: Parameter, incomplete: str
    ) -> list[CompletionItem]:
        """Complete file paths for this value."""
        from .shell_completion import CompletionItem

        return [CompletionItem(incomplete, type="file")]

    def resolve_lazy_flag(self, value: t.Any) -> bool:
        if self.lazy is not None:
            return bool(self.lazy)
        if os.fspath(value) == "-":
            return False
        if "w" in self.mode or "x" in self.mode or "a" in self.mode:
            return True
        return False

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        from ._files import LazyFile, KeepOpenFile
        from ._streams import open_stream

        if hasattr(value, "read") or hasattr(value, "write"):
            return value

        lazy = self.resolve_lazy_flag(value)
        if lazy:
            try:
                lf = LazyFile(
                    value, self.mode, self.encoding, self.errors, atomic=self.atomic
                )
            except OSError as e:
                self.fail(f"{os.fspath(value)!r}: {e.strerror}", param, ctx)
            if ctx is not None:
                ctx.call_on_close(lf.close_intelligently)
            return t.cast("t.IO[t.Any]", lf)

        try:
            rv, should_close = open_stream(
                value, self.mode, self.encoding, self.errors, atomic=self.atomic
            )
        except OSError as e:
            self.fail(f"{os.fspath(value)!r}: {e.strerror}", param, ctx)

        if ctx is not None:
            if should_close:
                ctx.call_on_close(_safe_close(rv))
            else:
                rv = t.cast("t.IO[t.Any]", KeepOpenFile(rv))
        return rv


def _safe_close(f: t.IO[t.Any]) -> t.Callable[[], None]:
    def _close() -> None:
        try:
            f.close()
        except OSError:
            pass

    return _close


class Path(ParamType):
    envvar_list_splitter = os.path.pathsep

    def __init__(
        self,
        exists: bool = False,
        file_okay: bool = True,
        dir_okay: bool = True,
        writable: bool = False,
        readable: bool = True,
        resolve_path: bool = False,
        allow_dash: bool = False,
        path_type: type | None = None,
        executable: bool = False,
    ) -> None:
        self.exists = exists
        self.file_okay = file_okay
        self.dir_okay = dir_okay
        self.writable = writable
        self.readable = readable
        self.resolve_path = resolve_path
        self.allow_dash = allow_dash
        self.type = path_type
        self.executable = executable

        if self.file_okay and not self.dir_okay:
            self.name: str = "file"
        elif self.dir_okay and not self.file_okay:
            self.name = "directory"
        else:
            self.name = "path"

    def to_info_dict(self) -> dict[str, t.Any]:
        info: dict[str, t.Any] = {
            "exists": self.exists,
            "file_okay": self.file_okay,
            "dir_okay": self.dir_okay,
            "writable": self.writable,
            "readable": self.readable,
            "allow_dash": self.allow_dash,
        }
        info.update(super().to_info_dict())
        return info

    def shell_complete(
        self, ctx: Context, param: Parameter, incomplete: str
    ) -> list[CompletionItem]:
        """Complete file or directory paths, depending on what is allowed."""
        from .shell_completion import CompletionItem

        kind = "dir" if self.dir_okay and not self.file_okay else "file"
        return [CompletionItem(incomplete, type=kind)]

    def coerce_path_result(
        self, value: str | os.PathLike[str]
    ) -> str | bytes | os.PathLike[str]:
        if self.type is not None and not isinstance(value, self.type):
            if self.type is bytes:
                return os.fsencode(value)
            if self.type is str:
                return os.fsdecode(value)
            return self.type(value)  # type: ignore[call-arg]
        return value

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> t.Any:
        rv = value
        is_dash = self.file_okay and self.allow_dash and rv in ("-", b"-")

        if not is_dash:
            if self.resolve_path:
                rv = os.path.realpath(os.path.expanduser(os.fspath(rv)))

            try:
                st = os.stat(rv)
            except OSError:
                if not self.exists:
                    return self.coerce_path_result(rv)
                self.fail(
                    f"{self.name.title()} {format_filename(rv)!r} does not exist.",
                    param,
                    ctx,
                )

            if not self.file_okay and stat.S_ISREG(st.st_mode):
                self.fail(
                    f"{self.name.title()} {format_filename(rv)!r} is a file.", param, ctx
                )
            if not self.dir_okay and stat.S_ISDIR(st.st_mode):
                self.fail(
                    f"{self.name.title()} {format_filename(rv)!r} is a directory.",
                    param,
                    ctx,
                )
            if self.readable and not os.access(rv, os.R_OK):
                self.fail(
                    f"{self.name.title()} {format_filename(rv)!r} is not readable.",
                    param,
                    ctx,
                )
            if self.writable and not os.access(rv, os.W_OK):
                self.fail(
                    f"{self.name.title()} {format_filename(rv)!r} is not writable.",
                    param,
                    ctx,
                )
            if self.executable and not os.access(rv, os.X_OK):
                self.fail(
                    f"{self.name.title()} {format_filename(rv)!r} is not executable.",
                    param,
                    ctx,
                )

        return self.coerce_path_result(rv)


def convert_type(ty: t.Any | None = None, default: t.Any = None) -> ParamType:
    """Pick a :class:`ParamType` for a declared type and/or a default value."""
    guessed_type = False
    if ty is None and default is not None:
        if isinstance(default, (tuple, list)):
            if default:
                ty = type(default[0])
        else:
            ty = type(default)
        guessed_type = True

    if isinstance(ty, ParamType):
        return ty
    if ty is None or ty is str:
        return STRING
    if isinstance(ty, tuple):
        return Tuple(ty)

    if ty is int:
        return INT
    if ty is float:
        return FLOAT
    if ty is bool:
        return BOOL

    if guessed_type:
        return STRING

    if callable(ty):
        return FuncParamType(ty)

    return STRING


# Singletons
STRING = StringParamType()
INT = IntParamType()
FLOAT = FloatParamType()
BOOL = BoolParamType()
UUID = UUIDParameterType()
UNPROCESSED = UnprocessedParamType()


# ---------------------------------------------------------------------------
# Info-dict shapes (reference TypedDicts for the public surface).
# ---------------------------------------------------------------------------

class ParamTypeInfoDict(t.TypedDict):
    param_type: str
    name: str


class ChoiceInfoDict(ParamTypeInfoDict):
    choices: t.Sequence[t.Any]
    case_sensitive: bool


class DateTimeInfoDict(ParamTypeInfoDict):
    formats: list[str]


class FileInfoDict(ParamTypeInfoDict):
    mode: str
    encoding: str | None


class FuncParamTypeInfoDict(ParamTypeInfoDict):
    func: t.Callable[[t.Any], t.Any]


class NumberRangeInfoDict(ParamTypeInfoDict):
    min: t.Any
    max: t.Any
    min_open: bool
    max_open: bool
    clamp: bool


class PathInfoDict(ParamTypeInfoDict):
    exists: bool
    file_okay: bool
    dir_okay: bool
    writable: bool
    readable: bool
    allow_dash: bool


class TupleInfoDict(ParamTypeInfoDict):
    types: list[dict[str, t.Any]]


class OptionHelpExtra(t.TypedDict, total=False):
    envvar: str
    default: str
    range: str
    required: str
