"""Run the same program against clirelay and the oracle and compare channels."""
from __future__ import annotations

import typing as t

import clirelay

from ._oracle import load_oracle
from .normalize import normalize

Builder = t.Callable[[t.Any], t.Any]


class Mismatch(t.NamedTuple):
    channel: str
    oracle: t.Any
    mine: t.Any


def _testing_module(mod: t.Any) -> t.Any:
    import importlib

    return importlib.import_module(f"{mod.__name__}.testing")


def _invoke(mod: t.Any, cli: t.Any, args: t.Any, env: t.Any, inp: t.Any,
            prog_name: str, color: bool, standalone: bool,
            ctx_extra: dict[str, t.Any] | None = None) -> dict[str, t.Any]:
    runner = _testing_module(mod).CliRunner()
    extra: dict[str, t.Any] = {"prog_name": prog_name}
    if ctx_extra:
        extra.update(ctx_extra)
    if not standalone:
        extra["standalone_mode"] = False
    try:
        result = runner.invoke(
            cli, args, input=inp, env=env, color=color, **extra
        )
    except BaseException as exc:  # a CliRunner should not raise, but be safe
        return {"runner_error": (type(exc).__name__, str(exc))}
    exc = result.exception
    exc_repr = None
    if exc is not None and not isinstance(exc, SystemExit):
        exc_repr = (type(exc).__name__, str(exc))
    return {
        "exit_code": result.exit_code,
        "output": result.output,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exception": exc_repr,
        "return_value": result.return_value if not standalone else None,
    }


def run_both(
    build: Builder,
    args: t.Sequence[str] | None = None,
    env: t.Mapping[str, str] | None = None,
    input: str | None = None,
    prog_name: str = "cli",
    color: bool = False,
    standalone: bool = True,
    compare_return: bool = False,
    terminal_width: int | None = None,
    max_content_width: int | None = None,
) -> list[Mismatch]:
    """Build *build* with both libraries, run both, return any channel mismatches."""
    click = load_oracle()

    oracle_cli = build(click)
    mine_cli = build(clirelay)

    extra: dict[str, t.Any] = {}
    if terminal_width is not None:
        extra["terminal_width"] = terminal_width
    if max_content_width is not None:
        extra["max_content_width"] = max_content_width

    o = _invoke(click, oracle_cli, args, env, input, prog_name, color, standalone, extra)
    m = _invoke(clirelay, mine_cli, args, env, input, prog_name, color, standalone, extra)

    mismatches: list[Mismatch] = []
    channels = ["exit_code", "output", "stdout", "stderr", "exception"]
    if compare_return:
        channels.append("return_value")
    if "runner_error" in o or "runner_error" in m:
        channels = ["runner_error"]

    for ch in channels:
        ov = o.get(ch)
        mv = m.get(ch)
        if isinstance(mv, str):
            mv = normalize(mv)
        if isinstance(ov, tuple):
            ov = tuple(x for x in ov)
        if isinstance(mv, tuple):
            mv = tuple(normalize(x) if isinstance(x, str) else x for x in mv)
        if ov != mv:
            mismatches.append(Mismatch(ch, ov, mv))
    return mismatches


def to_info_dicts(build_param: t.Callable[[t.Any], t.Any]) -> tuple[t.Any, t.Any]:
    """Return (oracle_info, mine_info) for an object built by *build_param*."""
    click = load_oracle()
    o = build_param(click)
    m = build_param(clirelay)
    return o, m
