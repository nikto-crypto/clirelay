"""Realistic CLI builders used by the differential tests.

Each builder takes a Click-compatible module ``c`` and returns a command, so the
same program can be constructed against clirelay and against the oracle.  None of
these are copied from anywhere; they are written for this project.
"""
from __future__ import annotations

import enum
import typing as t

Builder = t.Callable[[t.Any], t.Any]

# A registry of (name, builder, [argv, ...]) tuples.
CASES: list[tuple[str, Builder, list[list[str]]]] = []


def register(name: str, argvs: list[list[str]]) -> t.Callable[[Builder], Builder]:
    def deco(fn: Builder) -> Builder:
        CASES.append((name, fn, argvs))
        return fn

    return deco


@register("greet", [
    ["--help"], [], ["world"], ["world", "extra"],
    ["-c", "3", "world"], ["--count", "x", "world"], ["-c"],
    ["--name=Al", "world"], ["-vvv", "world"], ["--bad"], ["--", "--weird"],
])
def greet(c: t.Any) -> t.Any:
    @c.command()
    @c.option("--count", "-c", default=1, help="How many times to greet.")
    @c.option("--name", help="Name of the person.")
    @c.option("--shout/--no-shout", default=False, help="Use capitals.")
    @c.option("-v", "--verbose", count=True, help="Be louder each time.")
    @c.argument("target")
    def cli(count: int, name: str, shout: bool, verbose: int, target: str) -> None:
        """Greet a target.

        Repeats the greeting a number of times.
        """
        c.echo(f"{count}|{name}|{shout}|{verbose}|{target}")

    return cli


@register("pkgtool", [
    ["--help"], [], ["install", "--help"], ["install", "requests"],
    ["install", "-U", "requests", "flask"], ["remove", "flask"],
    ["list"], ["nope"], ["instal"], ["install"],
])
def pkgtool(c: t.Any) -> t.Any:
    @c.group(help="A tiny package manager.")
    @c.option("--verbose", is_flag=True, help="Show more output.")
    @c.pass_context
    def cli(ctx: t.Any, verbose: bool) -> None:
        ctx.obj = {"verbose": verbose}

    @cli.command()
    @c.option("-U", "--upgrade", is_flag=True, help="Upgrade if installed.")
    @c.argument("packages", nargs=-1, required=True)
    def install(upgrade: bool, packages: tuple[str, ...]) -> None:
        """Install one or more packages."""
        c.echo(f"install upgrade={upgrade} {list(packages)}")

    @cli.command()
    @c.argument("package")
    def remove(package: str) -> None:
        """Remove a package."""
        c.echo(f"remove {package}")

    @cli.command(name="list")
    def list_(  # noqa: A001
    ) -> None:
        """List installed packages."""
        c.echo("listing")

    return cli


class Color(enum.Enum):
    RED = "r"
    GREEN = "g"
    BLUE = "b"


@register("typed", [
    ["--help"], ["--level", "5"], ["--level", "x"], ["--level", "20"],
    ["--ratio", "0.5"], ["--ratio", "2"], ["--color", "RED"], ["--color", "z"],
    ["--mode", "fast"], ["--mode", "FAST"], ["--when", "2020-01-02"],
    ["--when", "nope"], ["--pair", "1", "2"], ["--pair", "1"],
    ["a", "b", "c"], ["--tags", "x", "--tags", "y"],
])
def typed(c: t.Any) -> t.Any:
    @c.command()
    @c.option("--level", type=c.IntRange(0, 10, clamp=True), default=1)
    @c.option("--ratio", type=c.FloatRange(0, 1))
    @c.option("--color", type=c.Choice(Color))
    @c.option("--mode", type=c.Choice(["fast", "slow"], case_sensitive=False))
    @c.option("--when", type=c.DateTime())
    @c.option("--pair", nargs=2, type=int)
    @c.option("--tags", multiple=True)
    @c.argument("names", nargs=-1)
    def cli(level, ratio, color, mode, when, pair, tags, names):  # type: ignore[no-untyped-def]
        c.echo(f"{level}|{ratio}|{color}|{mode}|{when}|{pair}|{tags}|{names}")

    return cli


@register("server", [
    ["--help"], ["--host", "0.0.0.0", "--port", "9000"],
    ["--port", "notaport"], ["--reload"], ["--no-reload"],
    ["--workers", "4"], ["--port"],
])
def server(c: t.Any) -> t.Any:
    @c.command(help="Run a development server.")
    @c.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
    @c.option("--port", "-p", default=8000, show_default=True, type=int, help="Bind port.")
    @c.option("--reload/--no-reload", default=True, help="Auto reload on change.")
    @c.option("--workers", type=c.IntRange(1, 16), default=1, show_default=True)
    def cli(host: str, port: int, reload: bool, workers: int) -> None:
        c.echo(f"serving {host}:{port} reload={reload} workers={workers}")

    return cli


@register("chained", [
    ["--help"], [], ["open", "process", "save"], ["open"],
    ["open", "nope"],
])
def chained(c: t.Any) -> t.Any:
    @c.group(chain=True, invoke_without_command=True, help="A pipeline.")
    def cli() -> None:
        pass

    @cli.command()
    def open() -> None:  # noqa: A001
        """Open a source."""
        c.echo("open")

    @cli.command()
    def process() -> None:
        """Process the data."""
        c.echo("process")

    @cli.command()
    def save() -> None:
        """Save the result."""
        c.echo("save")

    return cli


@register("required_opts", [
    ["--help"], [], ["--name", "x"], ["--name", "x", "--token", "t"],
])
def required_opts(c: t.Any) -> t.Any:
    @c.command()
    @c.option("--name", required=True, help="Required name.")
    @c.option("--token", envvar="APP_TOKEN", help="Auth token.")
    def cli(name: str, token: str) -> None:
        c.echo(f"{name}|{token}")

    return cli


@register("deprecated", [
    ["--help"], ["--old", "x"], ["--new", "y"],
])
def deprecated(c: t.Any) -> t.Any:
    @c.command()
    @c.option("--old", deprecated=True, help="Old.")
    @c.option("--older", deprecated="use --new", help="Older.")
    @c.option("--new", help="New.")
    def cli(old: str, older: str, new: str) -> None:
        c.echo(f"{old}|{older}|{new}")

    return cli
