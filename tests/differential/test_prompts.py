"""Differential tests for prompts and confirmation under scripted input."""
from __future__ import annotations

import pytest

from .harness import run_both


def _prompt_name(c):
    @c.command()
    @c.option("--name", prompt=True)
    def cli(name):
        c.echo(f"name={name}")
    return cli


def _prompt_int(c):
    @c.command()
    @c.option("--count", prompt="How many", type=int)
    def cli(count):
        c.echo(f"count={count}")
    return cli


def _prompt_default(c):
    @c.command()
    @c.option("--name", prompt=True, default="world")
    def cli(name):
        c.echo(f"name={name}")
    return cli


def _prompt_confirm(c):
    @c.command()
    @c.option("--pw", prompt=True, confirmation_prompt=True)
    def cli(pw):
        c.echo(f"pw={pw}")
    return cli


def _prompt_hidden(c):
    @c.command()
    @c.option("--pw", prompt=True, hide_input=True, type=int)
    def cli(pw):
        c.echo(f"pw={pw}")
    return cli


def _prompt_choice(c):
    @c.command()
    @c.option("--color", prompt=True, type=c.Choice(["r", "g"]))
    def cli(color):
        c.echo(f"color={color}")
    return cli


def _confirm_cmd(c):
    @c.command()
    @c.option("--yes", is_flag=True, prompt="Continue")
    def cli(yes):
        c.echo(f"yes={yes}")
    return cli


CASES = [
    (_prompt_name, "Alice\n"),
    (_prompt_name, ""),
    (_prompt_int, "5\n"),
    (_prompt_int, "x\n7\n"),
    (_prompt_default, "\n"),
    (_prompt_default, "Bob\n"),
    (_prompt_confirm, "secret\nsecret\n"),
    (_prompt_confirm, "secret\nother\nsame\nsame\n"),
    (_prompt_hidden, "notanint\n42\n"),
    (_prompt_choice, "r\n"),
    (_prompt_choice, "x\ng\n"),
    (_confirm_cmd, "y\n"),
    (_confirm_cmd, "n\n"),
]


@pytest.mark.parametrize(
    "builder,inp",
    CASES,
    ids=[f"{b.__name__}:{inp!r}" for b, inp in CASES],
)
def test_prompt(builder, inp):
    mismatches = run_both(builder, [], input=inp)
    assert not mismatches, "\n".join(
        f"[{m.channel}]\n  oracle={m.oracle!r}\n  mine=  {m.mine!r}" for m in mismatches
    )
