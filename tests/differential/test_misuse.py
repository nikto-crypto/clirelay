"""Differential tests for API misuse (channel 10): same error class and message."""
from __future__ import annotations

import pytest

import importlib

import clirelay

from ._oracle import load_oracle
from .normalize import normalize


def _err(fn):
    try:
        fn()
        return ("<no error>", "")
    except BaseException as e:  # noqa: BLE001
        return (type(e).__name__, normalize(str(e)))


def _cmp(ofn, cfn):
    o = _err(ofn)
    c = _err(cfn)
    # error message text for TypeErrors naming private helpers is exempt; we
    # still require the same class for those.
    assert o[0] == c[0], f"class mismatch: oracle={o} mine={c}"
    return o, c


def test_command_cls_positional():
    click = load_oracle()

    def misuse(mod):
        @mod.command(mod.Command)
        def f():
            pass

    o, c = _cmp(lambda: misuse(click), lambda: misuse(clirelay))
    assert o == c


def test_convert_twice():
    click = load_oracle()

    def misuse(mod):
        @mod.command()
        @mod.command()
        def f():
            pass

    o, c = _cmp(lambda: misuse(click), lambda: misuse(clirelay))
    assert o == c


def test_deprecated_required_option():
    click = load_oracle()
    o, c = _cmp(
        lambda: click.Option(["--q"], deprecated=True, required=True),
        lambda: clirelay.Option(["--q"], deprecated=True, required=True),
    )
    assert o == c


def test_make_pass_decorator_missing():
    click = load_oracle()

    class Repo:
        pass

    def run(mod):
        @mod.command()
        @mod.make_pass_decorator(Repo)
        def cli(repo):
            pass

        return importlib.import_module(f'{mod.__name__}.testing').CliRunner().invoke(cli, [], prog_name="cli")

    ro = run(click)
    rc = run(clirelay)
    assert type(ro.exception).__name__ == type(rc.exception).__name__
    assert normalize(str(rc.exception)) == str(ro.exception)


def test_get_current_context_outside():
    click = load_oracle()
    o, c = _cmp(
        lambda: click.get_current_context(),
        lambda: clirelay.get_current_context(),
    )
    assert o == c


def test_floatrange_clamp_open():
    click = load_oracle()
    o, c = _cmp(
        lambda: click.FloatRange(0, 1, max_open=True, clamp=True),
        lambda: clirelay.FloatRange(0, 1, max_open=True, clamp=True),
    )
    assert o == c


@pytest.mark.parametrize("bad", ["nope", (1, 2), 256])
def test_style_unknown_color(bad):
    click = load_oracle()
    o, c = _cmp(
        lambda: click.style("x", fg=bad), lambda: clirelay.style("x", fg=bad)
    )
    assert o == c


def test_custom_version_option_exists():
    click = load_oracle()
    assert hasattr(click, "custom_version_option")
    assert hasattr(clirelay, "custom_version_option")


def test_duplicate_parameter_warning():
    """Duplicate parameter names emit a matching UserWarning."""
    import warnings

    click = load_oracle()

    def build_and_run(mod):
        @mod.command()
        @mod.option("-a", "--alpha")
        @mod.option("-a", "--another")
        def cli(alpha, another):
            pass

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.import_module(f'{mod.__name__}.testing').CliRunner().invoke(cli, ["--help"], prog_name="cli")
        return [
            (w.category.__name__, normalize(str(w.message)))
            for w in caught
            if w.category is UserWarning
        ]

    o = build_and_run(click)
    c = build_and_run(clirelay)
    assert o == c, f"oracle={o} mine={c}"
