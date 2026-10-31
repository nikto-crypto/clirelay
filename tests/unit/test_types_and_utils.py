"""Original unit tests for parameter types and utility functions."""
from __future__ import annotations

import io

import pytest

import clirelay


def test_int_convert():
    assert clirelay.INT.convert("42", None, None) == 42
    with pytest.raises(clirelay.BadParameter):
        clirelay.INT.convert("x", None, None)


def test_bool_convert():
    assert clirelay.BOOL.convert("yes", None, None) is True
    assert clirelay.BOOL.convert("", None, None) is False
    with pytest.raises(clirelay.BadParameter):
        clirelay.BOOL.convert("maybe", None, None)


def test_intrange_clamp():
    assert clirelay.IntRange(0, 10, clamp=True).convert("11", None, None) == 10
    with pytest.raises(clirelay.BadParameter):
        clirelay.IntRange(0, 10).convert("11", None, None)


def test_floatrange_open_clamp_rejected():
    with pytest.raises(TypeError):
        clirelay.FloatRange(0, 1, max_open=True, clamp=True)


def test_choice_case_insensitive():
    c = clirelay.Choice(["Red", "Blue"], case_sensitive=False)
    assert c.convert("red", None, None) == "Red"


def test_to_info_dict_shapes():
    assert clirelay.INT.to_info_dict() == {"param_type": "Int", "name": "integer"}
    assert clirelay.STRING.to_info_dict() == {"param_type": "String", "name": "text"}


def test_style_and_unstyle():
    styled = clirelay.style("x", fg="red")
    assert styled == "\x1b[31mx\x1b[0m"
    assert clirelay.unstyle(styled) == "x"
    with pytest.raises(ValueError):
        clirelay.style("x", fg="nope")


def test_echo_strips_when_not_tty():
    buf = io.StringIO()
    clirelay.echo(clirelay.style("x", fg="red"), file=buf)
    assert buf.getvalue() == "x\n"


def test_wrap_text():
    text = "word " * 10
    wrapped = clirelay.wrap_text(text.strip(), width=20)
    assert all(len(line) <= 20 for line in wrapped.splitlines())


def test_format_filename():
    assert clirelay.format_filename("/a/b/c.txt", shorten=True) == "c.txt"


def test_param_type_subscriptable():
    class URL(clirelay.ParamType[str]):
        name = "url"

    assert URL().name == "url"


def test_repr():
    @clirelay.command()
    def thing():
        pass

    assert repr(thing) == "<Command thing>"
    assert repr(clirelay.BOOL) == "BOOL"
