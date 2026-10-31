"""Original unit tests for commands, options, and arguments.

These assert clirelay's behavior directly, so the suite stands alone without the
oracle.
"""
from __future__ import annotations

import enum

import pytest

import clirelay
from clirelay.testing import CliRunner


@pytest.fixture()
def runner():
    return CliRunner()


def test_basic_command(runner):
    @clirelay.command()
    @clirelay.option("--count", default=1)
    @clirelay.argument("name")
    def cli(count, name):
        for _ in range(count):
            clirelay.echo(f"hi {name}")

    result = runner.invoke(cli, ["--count", "2", "bob"])
    assert result.exit_code == 0
    assert result.output == "hi bob\nhi bob\n"


def test_missing_argument(runner):
    @clirelay.command()
    @clirelay.argument("name")
    def cli(name):
        pass

    result = runner.invoke(cli, [])
    assert result.exit_code == 2
    assert "Missing argument 'NAME'." in result.output


def test_unknown_option_suggestion(runner):
    @clirelay.command()
    @clirelay.option("--sort")
    def cli(sort):
        pass

    result = runner.invoke(cli, ["--sot"])
    assert result.exit_code == 2
    assert "No such option '--sot'. Did you mean '--sort'?" in result.output


def test_flag_pair_default(runner):
    @clirelay.command()
    @clirelay.option("--shout/--no-shout", default=True)
    def cli(shout):
        clirelay.echo(str(shout))

    assert runner.invoke(cli, []).output == "True\n"
    assert runner.invoke(cli, ["--no-shout"]).output == "False\n"


def test_count_option(runner):
    @clirelay.command()
    @clirelay.option("-v", "--verbose", count=True)
    def cli(verbose):
        clirelay.echo(str(verbose))

    assert runner.invoke(cli, ["-vvv"]).output == "3\n"
    assert runner.invoke(cli, []).output == "0\n"


def test_multiple_option(runner):
    @clirelay.command()
    @clirelay.option("--tag", multiple=True)
    def cli(tag):
        clirelay.echo(repr(tag))

    assert runner.invoke(cli, ["--tag", "a", "--tag", "b"]).output == "('a', 'b')\n"


def test_variadic_argument(runner):
    @clirelay.command()
    @clirelay.argument("files", nargs=-1)
    def cli(files):
        clirelay.echo(repr(files))

    assert runner.invoke(cli, ["x", "y", "z"]).output == "('x', 'y', 'z')\n"


def test_group_dispatch(runner):
    @clirelay.group()
    def cli():
        pass

    @cli.command()
    def sub():
        clirelay.echo("ran sub")

    assert runner.invoke(cli, ["sub"]).output == "ran sub\n"
    assert runner.invoke(cli, []).exit_code == 2


def test_choice_enum(runner):
    class Color(enum.Enum):
        RED = "r"
        BLUE = "b"

    @clirelay.command()
    @clirelay.option("--color", type=clirelay.Choice(Color))
    def cli(color):
        clirelay.echo(color.name if color else "none")

    assert runner.invoke(cli, ["--color", "RED"]).output == "RED\n"
    bad = runner.invoke(cli, ["--color", "x"])
    assert "'x' is not one of 'RED', 'BLUE'." in bad.output


def test_command_name_derivation():
    @clirelay.command()
    def init_cmd():
        pass

    assert init_cmd.name == "init"


def test_return_value_non_standalone():
    @clirelay.command()
    @clirelay.option("--n", type=int, default=2)
    def cli(n):
        return n * 10

    assert cli(["--n", "3"], standalone_mode=False) == 30
