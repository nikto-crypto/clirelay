"""Original unit tests for help rendering and error reporting."""
from __future__ import annotations

import clirelay
from clirelay.testing import CliRunner


def test_help_layout():
    @clirelay.command()
    @clirelay.option("--count", "-c", default=1, help="How many.")
    @clirelay.argument("name")
    def cli(count, name):
        """Greet someone."""

    result = CliRunner().invoke(cli, ["--help"], prog_name="greet", terminal_width=80)
    assert result.exit_code == 0
    assert "Usage: greet [OPTIONS] NAME" in result.output
    assert "Greet someone." in result.output
    assert "-c, --count INTEGER  How many." in result.output
    assert "--help" in result.output


def test_usage_error_banner():
    @clirelay.command()
    @clirelay.option("--x")
    def cli(x):
        pass

    result = CliRunner().invoke(cli, ["--bad"], prog_name="cli")
    assert result.exit_code == 2
    assert result.output.startswith("Usage: cli [OPTIONS]\n")
    assert "Try 'cli --help' for help." in result.output
    assert "Error: No such option '--bad'." in result.output


def test_missing_value_has_no_banner():
    @clirelay.command()
    @clirelay.option("--port", type=int)
    def cli(port):
        pass

    result = CliRunner().invoke(cli, ["--port"], prog_name="cli")
    assert result.output == "Error: Option '--port' requires an argument.\n"


def test_clickexception_exit_code():
    @clirelay.command()
    def cli():
        raise clirelay.ClickException("boom")

    result = CliRunner().invoke(cli, [])
    assert result.exit_code == 1
    assert result.output == "Error: boom\n"


def test_abort():
    @clirelay.command()
    def cli():
        raise clirelay.Abort()

    result = CliRunner().invoke(cli, [])
    assert result.exit_code == 1
    assert result.stderr == "Aborted!\n"


def test_show_default_in_help():
    @clirelay.command()
    @clirelay.option("--host", default="localhost", show_default=True, help="Host.")
    def cli(host):
        pass

    out = CliRunner().invoke(cli, ["--help"], terminal_width=80).output
    assert "[default: localhost]" in out
