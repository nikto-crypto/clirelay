"""clirelay — a composable command-line interface toolkit.

Define commands by decorating functions, group them into trees, and let clirelay
handle parsing, type conversion, help output, prompting, and shell completion.
"""
from __future__ import annotations

import typing as t

from .core import (
    Argument as Argument,
    Command as Command,
    CommandCollection as CommandCollection,
    Context as Context,
    Group as Group,
    Option as Option,
    Parameter as Parameter,
    ParameterSource as ParameterSource,
)
from .decorators import (
    argument as argument,
    command as command,
    confirmation_option as confirmation_option,
    custom_version_option as custom_version_option,
    group as group,
    help_option as help_option,
    make_pass_decorator as make_pass_decorator,
    option as option,
    pass_context as pass_context,
    pass_obj as pass_obj,
    password_option as password_option,
    version_option as version_option,
)
from .exceptions import (
    Abort as Abort,
    BadArgumentUsage as BadArgumentUsage,
    BadOptionUsage as BadOptionUsage,
    BadParameter as BadParameter,
    ClickException as ClickException,
    FileError as FileError,
    MissingParameter as MissingParameter,
    NoSuchCommand as NoSuchCommand,
    NoSuchOption as NoSuchOption,
    UsageError as UsageError,
)
from .formatting import HelpFormatter as HelpFormatter, wrap_text as wrap_text
from .globals import get_current_context as get_current_context
from .termui import (
    clear as clear,
    confirm as confirm,
    echo_via_pager as echo_via_pager,
    edit as edit,
    get_pager_file as get_pager_file,
    getchar as getchar,
    launch as launch,
    pause as pause,
    progressbar as progressbar,
    prompt as prompt,
    secho as secho,
    style as style,
    unstyle as unstyle,
)
from .types import (
    BOOL as BOOL,
    Choice as Choice,
    DateTime as DateTime,
    FLOAT as FLOAT,
    File as File,
    FloatRange as FloatRange,
    INT as INT,
    IntRange as IntRange,
    ParamType as ParamType,
    Path as Path,
    STRING as STRING,
    Tuple as Tuple,
    UNPROCESSED as UNPROCESSED,
    UUID as UUID,
)
from .utils import (
    echo as echo,
    format_filename as format_filename,
    get_app_dir as get_app_dir,
    open_file as open_file,
)

_DEPRECATED_MESSAGES = {
    "BaseCommand": "'BaseCommand' is deprecated and will be removed in Click 9.0. Use 'Command' instead.",
    "MultiCommand": "'MultiCommand' is deprecated and will be removed in Click 9.0. Use 'Group' instead.",
    "OptionParser": "'OptionParser' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'.",
    "get_binary_stream": "'get_binary_stream' is deprecated and will be removed in Click 9.0.",
    "get_text_stream": "'get_text_stream' is deprecated and will be removed in Click 9.0.",
}


def __getattr__(name: str) -> t.Any:
    import warnings

    if name == "__version__":
        warnings.warn(
            "The '__version__' attribute is deprecated and will be removed in "
            'Click 9.1. Use feature detection or \'importlib.metadata.version("clirelay")\' '
            "instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        import importlib.metadata

        return importlib.metadata.version("clirelay")

    if name in _DEPRECATED_MESSAGES:
        warnings.warn(_DEPRECATED_MESSAGES[name], DeprecationWarning, stacklevel=2)
        if name == "BaseCommand":
            from .core import Command as _C

            return _C
        if name == "MultiCommand":
            from .core import Group as _G

            return _G
        if name == "OptionParser":
            from ._parsing import _Parser

            return _Parser
        if name == "get_binary_stream":
            from ._streams import get_binary_stream

            return get_binary_stream
        if name == "get_text_stream":
            from ._streams import get_text_stream

            return get_text_stream

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
