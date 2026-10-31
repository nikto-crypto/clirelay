"""Differential tests covering the independent review's findings (#1-#13).

These lock in behaviors the earlier suite under-exercised. #11 (the default help
parameter's internal name) is exempt by the build contract and is not asserted.
"""
from __future__ import annotations

import importlib
import io

import pytest

import clirelay

from ._oracle import load_oracle
from .harness import run_both
from .normalize import normalize


def _assert_match(builder, **kw):
    mismatches = run_both(builder, **kw)
    assert not mismatches, "\n".join(
        f"[{m.channel}] oracle={m.oracle!r} mine={m.mine!r}" for m in mismatches
    )


# #1 auto_envvar_prefix resolves a value
def test_auto_envvar_prefix():
    def build(c):
        @c.command(context_settings={"auto_envvar_prefix": "APP"})
        @c.option("--name")
        def cli(name):
            c.echo(repr(name))
        return cli

    _assert_match(build, args=[], env={"APP_NAME": "fromenv"})
    _assert_match(build, args=["--name", "cli"], env={"APP_NAME": "fromenv"})


# #2 File(lazy=True) missing file -> usage error
def test_file_lazy_missing():
    def build(c):
        @c.command()
        @c.argument("f", type=c.File(lazy=True))
        def cli(f):
            c.echo(f.name)
        return cli

    _assert_match(build, args=["nope_does_not_exist.txt"])


# #3 CliRunner streams report a name
def test_dash_file_name():
    def build(c):
        @c.command()
        @c.argument("f", type=c.File("w"))
        def cli(f):
            c.echo(f.name)
        return cli

    _assert_match(build, args=["-"])


# #4 HelpFormatter auto width (COLUMNS fixed at 80 by conftest)
@pytest.mark.parametrize("max_width", [None, 60, 40, 200])
def test_helpformatter_auto_width(max_width):
    click = load_oracle()
    ofmt = importlib.import_module("click.formatting")
    assert ofmt.HelpFormatter(max_width=max_width).width == \
        clirelay.formatting.HelpFormatter(max_width=max_width).width


# #5 usage error from inside a callback keeps the "Try ... --help" hint
@pytest.mark.parametrize("raiser", ["bad_arg", "usage", "bad_param", "missing"])
def test_callback_usageerror_hint(raiser):
    def build(c):
        @c.command()
        @c.argument("x")
        def cli(x):
            if raiser == "bad_arg":
                raise c.BadArgumentUsage("bad arg here")
            if raiser == "usage":
                raise c.UsageError("generic usage")
            if raiser == "bad_param":
                raise c.BadParameter("bad val", param_hint="--z")
            raise c.MissingParameter(param_hint="--z")
        return cli

    _assert_match(build, args=["v"])


# #6 progressbar on a non-terminal emits the label line
@pytest.mark.parametrize("label", ["work", None])
def test_progressbar_non_tty(label):
    click = load_oracle()

    def run(mod):
        buf = io.StringIO()
        with mod.progressbar([1, 2, 3], label=label, file=buf) as bar:
            for _ in bar:
                pass
        return buf.getvalue()

    assert run(click) == normalize(run(clirelay))


# #7 option prompt honors show_default
@pytest.mark.parametrize("show_default,inp", [(False, "\n"), ("custom", "\n"), (True, "\n")])
def test_prompt_show_default(show_default, inp):
    def build(c):
        @c.command()
        @c.option("--x", prompt=True, default="d", show_default=show_default)
        def cli(x):
            c.echo(x)
        return cli

    _assert_match(build, args=[], input=inp)


# #8 shared-destination flag default resolves to its flag_value
def test_shared_flag_default():
    def build(c):
        @c.command()
        @c.option("--upper", "transform", flag_value="upper")
        @c.option("--lower", "transform", flag_value="lower", default=True)
        def cli(transform):
            c.echo(transform)
        return cli

    _assert_match(build, args=[])
    _assert_match(build, args=["--upper"])


# #9 prompt_required=False
def test_prompt_required_false():
    def build(c):
        @c.command()
        @c.option("--name", prompt=True, prompt_required=False, default="d")
        def cli(name):
            c.echo(name)
        return cli

    _assert_match(build, args=[])
    _assert_match(build, args=["--name"], input="typed\n")
    _assert_match(build, args=["--name", "given"])


# #10 short-help ellipsis reserves its 3 chars
@pytest.mark.parametrize("limit", [45, 20, 13, 14])
def test_short_help(limit):
    click = load_oracle()
    HELP = "This is a very long first line of help text that should get truncated nicely."

    def make(mod):
        @mod.command(help=HELP)
        def cli():
            pass
        return cli.get_short_help_str(limit)

    assert make(click) == normalize(make(clirelay))


# #12 version_option auto-detection error handling
def test_version_option_no_package():
    def build(c):
        @c.command()
        @c.version_option()
        def cli():
            pass
        return cli

    _assert_match(build, args=["--version"])


def test_version_option_bad_package():
    def build(c):
        @c.command()
        @c.version_option(package_name="no_such_pkg_xyz_123")
        def cli():
            pass
        return cli

    _assert_match(build, args=["--version"])


# #13 echo_via_pager appends a newline on a non-terminal
@pytest.mark.parametrize("text", ["line1\nline2\n", "abc", ""])
def test_echo_via_pager_non_tty(text):
    def build(c):
        @c.command()
        def cli():
            c.echo_via_pager(text)
        return cli

    _assert_match(build, args=[])
