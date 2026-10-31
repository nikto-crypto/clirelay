"""Differential tests for shell completion: source scripts and responses."""
from __future__ import annotations

import importlib
import os

import pytest

import clirelay

from ._oracle import load_oracle
from .normalize import normalize

SHELLS = ["bash", "zsh", "fish", "powershell"]


def _sc(mod):
    return importlib.import_module(f"{mod.__name__}.shell_completion")


def _completion_group(mod):
    @mod.group()
    def cli():
        pass

    @cli.command()
    @mod.option("--verbose", is_flag=True)
    @mod.argument("name", type=mod.Choice(["alpha", "beta", "gamma"]))
    def build(verbose, name):
        pass

    @cli.command()
    @mod.option("--level", type=mod.Choice(["low", "high"]))
    def deploy(level):
        pass

    return cli


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("prog", ["my-prog", "tool", "x_y"])
def test_source_scripts(shell, prog):
    click = load_oracle()
    osc, csc = _sc(click), _sc(clirelay)
    o = osc.get_completion_class(shell)(
        _completion_group(click), {}, prog, f"_{prog.upper()}_COMPLETE"
    ).source()
    c = csc.get_completion_class(shell)(
        _completion_group(clirelay), {}, prog, f"_{prog.upper()}_COMPLETE"
    ).source()
    assert o == normalize(c), f"{shell}/{prog} source differs"


COMPLETION_CASES = [
    (["cli"], ""),      # subcommands
    (["cli"], "b"),     # subcommand prefix
    (["cli"], "de"),
    (["cli", "build"], ""),        # argument choices + options
    (["cli", "build"], "al"),      # choice prefix
    (["cli", "build"], "--"),      # options
    (["cli", "deploy", "--level"], ""),
    (["cli", "deploy"], "--l"),
]


@pytest.mark.parametrize("shell", ["bash", "zsh"])
@pytest.mark.parametrize("words,incomplete", COMPLETION_CASES)
def test_completion_response(shell, words, incomplete, monkeypatch):
    click = load_oracle()
    osc, csc = _sc(click), _sc(clirelay)

    comp_words = " ".join(words + ([incomplete] if incomplete else [""]))
    comp_cword = len(words)
    monkeypatch.setenv("COMP_WORDS", comp_words)
    monkeypatch.setenv("COMP_CWORD", str(comp_cword))

    def run(mod, sc):
        cls = sc.get_completion_class(shell)
        comp = cls(_completion_group(mod), {}, "cli", "_CLI_COMPLETE")
        return comp.complete()

    o = run(click, osc)
    c = normalize(run(clirelay, csc))
    assert o == c, (
        f"{shell} words={words} incomplete={incomplete!r}\n  O={o!r}\n  C={c!r}"
    )


def test_split_arg_string():
    click = load_oracle()
    osc, csc = _sc(click), _sc(clirelay)
    for s in ['a b c', 'a "b c" d', "a 'b c'", 'a\\ b', 'unterminated "quote', ""]:
        assert osc.split_arg_string(s) == csc.split_arg_string(s), f"split {s!r}"


def test_unknown_shell_source():
    """An unknown completion shell exits 1 and prints nothing (channel 7 trap)."""
    click = load_oracle()
    osc, csc = _sc(click), _sc(clirelay)
    assert osc.get_completion_class("nushell") is None
    assert csc.get_completion_class("nushell") is None
