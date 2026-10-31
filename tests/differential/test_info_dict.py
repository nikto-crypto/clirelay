"""Differential tests for to_info_dict on commands, contexts, and parameters."""
from __future__ import annotations

import enum

import pytest

import clirelay

from ._oracle import load_oracle
from .normalize import normalize


def _norm(obj):
    import json

    text = normalize(json.dumps(obj, default=repr, sort_keys=True))
    # The default help parameter's internal name is exempt from parity.
    return text.replace('"_click_default_help"', '"help"')


class Color(enum.Enum):
    RED = "r"
    BLUE = "b"


def _rich(c):
    @c.command(help="Do things.", epilog="Bye.")
    @c.option("--count", "-c", default=1, help="Count.")
    @c.option("--flag/--no-flag", default=True)
    @c.option("--multi", multiple=True)
    @c.option("--level", type=c.IntRange(0, 10))
    @c.option("--color", type=c.Choice(Color))
    @c.option("-v", "--verbose", count=True)
    @c.argument("src")
    @c.argument("dst", nargs=-1)
    def cli(count, flag, multi, level, color, verbose, src, dst):
        pass
    return cli


def _group(c):
    @c.group(chain=True)
    def cli():
        pass

    @cli.command()
    def one():
        pass

    @cli.command()
    def two():
        pass
    return cli


@pytest.mark.parametrize("builder", [_rich, _group], ids=["command", "group"])
def test_command_to_info_dict(builder):
    click = load_oracle()
    ocmd = builder(click)
    mcmd = builder(clirelay)
    octx = click.Context(ocmd, info_name="cli")
    mctx = clirelay.Context(mcmd, info_name="cli")
    assert _norm(ocmd.to_info_dict(octx)) == _norm(mcmd.to_info_dict(mctx))


def test_context_to_info_dict():
    click = load_oracle()
    octx = click.Context(_rich(click), info_name="cli", auto_envvar_prefix="APP")
    mctx = clirelay.Context(_rich(clirelay), info_name="cli", auto_envvar_prefix="APP")
    assert _norm(octx.to_info_dict()) == _norm(mctx.to_info_dict())


def test_option_to_info_dict_flag():
    """The exact flag info-dict from the build contract."""
    click = load_oracle()
    o = click.Option(["--flag/--no-flag"], default=True).to_info_dict()
    m = clirelay.Option(["--flag/--no-flag"], default=True).to_info_dict()
    assert o == m
    expected = {
        "name": "flag", "param_type_name": "option", "opts": ["--flag"],
        "secondary_opts": ["--no-flag"],
        "type": {"param_type": "Bool", "name": "boolean"},
        "required": False, "nargs": 1, "multiple": False, "default": True,
        "envvar": None, "help": None, "prompt": None, "is_flag": True,
        "flag_value": True, "count": False, "hidden": False,
    }
    assert m == expected


@pytest.mark.parametrize("decls,kwargs", [
    (["--x"], {}),
    (["--x", "-x"], {"type": int, "default": 3}),
    (["--opt"], {"type": clirelay.Choice(["a", "b"]), "required": True}),
    (["--files"], {"type": clirelay.File("r"), "multiple": True}),
    (["--p"], {"type": clirelay.Path(exists=True)}),
    (["--when"], {"type": clirelay.DateTime()}),
])
def test_parameter_to_info_dict(decls, kwargs):
    click = load_oracle()

    def make(mod):
        kw = dict(kwargs)
        ty = kw.get("type")
        if isinstance(ty, clirelay.ParamType):
            # rebuild type against the right module
            name = type(ty).__name__
            if name == "Choice":
                kw["type"] = mod.Choice(["a", "b"])
            elif name == "File":
                kw["type"] = mod.File("r")
            elif name == "Path":
                kw["type"] = mod.Path(exists=True)
            elif name == "DateTime":
                kw["type"] = mod.DateTime()
        return mod.Option(decls, **kw).to_info_dict()

    assert _norm(make(click)) == _norm(make(clirelay))
