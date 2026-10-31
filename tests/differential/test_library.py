"""Differential tests for public library functions (channel 5)."""
from __future__ import annotations

import io

import pytest

import clirelay

from ._oracle import load_oracle
from .normalize import normalize


def _both():
    return load_oracle(), clirelay


def _cmp(ofn, cfn):
    try:
        o = ofn()
        oerr = None
    except BaseException as e:  # noqa: BLE001
        o, oerr = None, (type(e).__name__, str(e))
    try:
        c = cfn()
        cerr = None
    except BaseException as e:  # noqa: BLE001
        c, cerr = None, (type(e).__name__, str(e))
    if oerr or cerr:
        assert oerr == (cerr if cerr is None else (cerr[0], normalize(cerr[1]))), (
            f"error mismatch: oracle={oerr} mine={cerr}"
        )
        return
    if isinstance(c, str):
        c = normalize(c)
    assert o == c, f"value mismatch: oracle={o!r} mine={c!r}"


STYLE_CASES = [
    dict(fg="red"), dict(fg=0), dict(fg=(1, 2, 3)), dict(bg="blue"),
    dict(fg="bright_red", bold=True), dict(underline=True, reset=False),
    dict(fg="green", bg="white", bold=True, underline=True, blink=True),
    dict(dim=True), dict(italic=True), dict(strikethrough=True), dict(overline=True),
    dict(reverse=True), dict(fg=255), dict(bg=(10, 20, 30)),
]


@pytest.mark.parametrize("kwargs", STYLE_CASES)
def test_style(kwargs):
    click, mine = _both()
    _cmp(lambda: click.style("sample", **kwargs), lambda: mine.style("sample", **kwargs))


@pytest.mark.parametrize("bad", ["nope", (1, 2), 256, -1, 1.5, (300, 0, 0)])
def test_style_errors(bad):
    click, mine = _both()
    _cmp(lambda: click.style("x", fg=bad), lambda: mine.style("x", fg=bad))


@pytest.mark.parametrize("text", [
    "\x1b[31mhi\x1b[0m", "plain", "\x1b[1m\x1b[4mbold\x1b[0m end",
    "\x1b]8;;http\x07osc\x1b]8;;\x07",
])
def test_unstyle(text):
    click, mine = _both()
    _cmp(lambda: click.unstyle(text), lambda: mine.unstyle(text))


@pytest.mark.parametrize("message", [
    "hello", "", None, 123, ["a", "b"], "\x1b[31mcolored\x1b[0m",
])
@pytest.mark.parametrize("nl", [True, False])
def test_echo(message, nl):
    click, mine = _both()

    def run(mod):
        buf = io.StringIO()
        mod.echo(message, file=buf, nl=nl)
        return buf.getvalue()

    _cmp(lambda: run(click), lambda: run(mine))


@pytest.mark.parametrize("message", ["styled", "plain"])
def test_secho(message):
    click, mine = _both()

    def run(mod):
        buf = io.StringIO()
        mod.secho(message, file=buf, fg="red", bold=True)
        return buf.getvalue()

    _cmp(lambda: run(click), lambda: run(mine))


WRAP_TEXTS = [
    "a short string",
    "word " * 30,
    "First.\n\nSecond paragraph that is a bit longer than the first one here now.",
    "\b\nkeep\n  these\n  lines\n\nbut wrap this part normally across the width now",
    "supercalifragilisticexpialidocious_single_unbreakable_token_goes_on_and_on",
]


@pytest.mark.parametrize("text", WRAP_TEXTS)
@pytest.mark.parametrize("width", [20, 40, 72])
@pytest.mark.parametrize("preserve", [True, False])
def test_wrap_text(text, width, preserve):
    click, mine = _both()
    _cmp(
        lambda: click.wrap_text(text, width, preserve_paragraphs=preserve),
        lambda: mine.wrap_text(text, width, preserve_paragraphs=preserve),
    )


@pytest.mark.parametrize("filename", [
    "/a/b/c.txt", b"/a/b/c.txt", "relative/path.py", b"/a/\xff/c",
])
@pytest.mark.parametrize("shorten", [True, False])
def test_format_filename(filename, shorten):
    click, mine = _both()
    _cmp(
        lambda: click.format_filename(filename, shorten=shorten),
        lambda: mine.format_filename(filename, shorten=shorten),
    )


@pytest.mark.parametrize("app", ["My App", "tool", "Weird Name 2"])
@pytest.mark.parametrize("posix", [True, False])
def test_get_app_dir(app, posix):
    click, mine = _both()
    _cmp(
        lambda: click.get_app_dir(app, force_posix=posix),
        lambda: mine.get_app_dir(app, force_posix=posix),
    )


def test_help_formatter():
    click, mine = _both()

    def build(mod):
        f = mod.HelpFormatter(width=50)
        f.write_usage("prog", "[OPTIONS] SRC DST")
        f.write_paragraph()
        with f.section("Options"):
            f.write_dl([("--foo", "Foo does a thing that wraps across the column."),
                        ("--bar", "Bar.")])
        return f.getvalue()

    _cmp(lambda: build(click), lambda: build(mine))
