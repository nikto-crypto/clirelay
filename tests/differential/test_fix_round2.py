"""Differential tests for the behaviors found by the second external evaluation.

The second evaluation drove both libraries through real processes and
pseudo-terminals, not only ``CliRunner``.  The decisive lesson is that the
visible echo of typed input belongs to ``CliRunner`` (it replaces the prompt
reader), never to the library itself.  So every prompt/interaction case here
runs three ways and all three must match the oracle:

* ``CliRunner`` (in process, via :func:`run_both`);
* a real subprocess with piped stdin;
* a pseudo-terminal (``pty``), where the terminal -- not the program -- echoes.

The remaining items (env-var list splitting, ``multiple`` with ``nargs``,
``DateTime`` singular message, name-less ``ParamType``, ``with_resource``
exceptions, undecodable path bytes, ``Group`` subclass hook order, completion at
the cursor, ``FloatRange`` open bounds) are exercised as whole classes too.
"""
from __future__ import annotations

import os
import select
import subprocess
import sys

import pytest

from ._oracle import ORACLE_DIR, load_oracle
from .harness import run_both
from .normalize import normalize

SRC = os.path.abspath("src")


def _assert_match(builder, **kw):
    mismatches = run_both(builder, **kw)
    assert not mismatches, "\n".join(
        f"[{m.channel}] oracle={m.oracle!r} mine={m.mine!r}" for m in mismatches
    )


# --------------------------------------------------------------------------
# Three-way process helpers.
# --------------------------------------------------------------------------

def _code(mod: str, root: str, body: str) -> str:
    return f"import sys; sys.path.insert(0, {root!r}); import {mod} as m\n{body}\n"


def _sub_io(mod: str, root: str, body: str, stdin: bytes, env: dict | None = None):
    """Run *body* as a real subprocess with piped stdin; return (rc, out, err)."""
    full = dict(os.environ)
    full.pop("NO_COLOR", None)
    full.update({"COLUMNS": "80", "TERM": "dumb"})
    if env:
        full.update(env)
    p = subprocess.run(
        [sys.executable, "-I", "-c", _code(mod, root, body)],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full,
        timeout=30,
    )
    return p.returncode, p.stdout, p.stderr


def _pty_io(mod: str, root: str, body: str, to_type: bytes) -> bytes:
    """Run *body* under a pty, type *to_type* after the first output, collect all."""
    import pty
    import time

    env = dict(os.environ, COLUMNS="80", LINES="24", TERM="xterm")
    env.pop("NO_COLOR", None)
    pid, fd = pty.fork()
    if pid == 0:
        os.environ.update(env)
        try:
            os.execv(sys.executable, [sys.executable, "-I", "-c", _code(mod, root, body)])
        finally:
            os._exit(127)
    out = b""
    sent = False
    deadline = time.time() + 8
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.4)
        if r:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        elif not sent and to_type is not None:
            # Wait for the prompt to appear before typing so hidden prompts have
            # disabled terminal echo first.
            if out:
                os.write(fd, to_type)
                sent = True
        done, _status = os.waitpid(pid, os.WNOHANG)
        if done:
            while True:
                r, _, _ = select.select([fd], [], [], 0.3)
                if not r:
                    break
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
            break
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.waitpid(pid, 0)
    except OSError:
        pass
    return out


def _three_way(body: str, stdin: str, *, env: dict | None = None, pty: bool = True):
    """Assert oracle and clirelay agree in subprocess and (optionally) pty modes."""
    load_oracle()
    b = stdin.encode()
    o_rc, o_out, o_err = _sub_io("click", ORACLE_DIR, body, b, env)
    m_rc, m_out, m_err = _sub_io("clirelay", SRC, body, b, env)
    assert o_rc == m_rc, f"subprocess rc {o_rc} != {m_rc}"
    assert o_out.decode() == normalize(m_out.decode()), (
        f"subprocess stdout\n oracle={o_out!r}\n mine  ={m_out!r}"
    )
    assert o_err.decode() == normalize(m_err.decode()), (
        f"subprocess stderr\n oracle={o_err!r}\n mine  ={m_err!r}"
    )
    if pty:
        po = _pty_io("click", ORACLE_DIR, body, b).decode("utf-8", "replace")
        pm = _pty_io("clirelay", SRC, body, b).decode("utf-8", "replace")
        assert po == normalize(pm), f"pty\n oracle={po!r}\n mine  ={pm!r}"


# --------------------------------------------------------------------------
# 1. Prompts do not echo input (echo belongs to CliRunner).
# --------------------------------------------------------------------------

_PROMPT_BODY = (
    "@m.command()\n"
    "@m.option('--name', prompt='Your name')\n"
    "def cli(name):\n    m.echo(f'Hello {name}!')\n"
    "cli([], prog_name='cli')\n"
)


@pytest.mark.parametrize("answer", ["John", "a b c", ""])
def test_prompt_no_echo_three_way(answer):
    # CliRunner (echo reappears via the replaced reader).
    def build(c):
        @c.command()
        @c.option("--name", prompt="Your name")
        def cli(name):
            c.echo(f"Hello {name}!")

        return cli

    _assert_match(build, input=answer + "\n")
    # Subprocess (no echo) + pty (terminal echoes once).
    _three_way(_PROMPT_BODY, (answer + "\n") if answer else "\n" + "x\n")


def test_prompt_err_stream_three_way():
    def build(c):
        @c.command()
        def cli():
            n = c.prompt("Name", err=True)
            c.echo(f"got {n}")

        return cli

    _assert_match(build, input="John\n")
    body = (
        "@m.command()\n"
        "def cli():\n    n = m.prompt('Name', err=True)\n    m.echo(f'got {n}')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, "John\n")


# --------------------------------------------------------------------------
# 2. Hidden input stays hidden (getpass; CliRunner reader does not echo).
# --------------------------------------------------------------------------

def test_hidden_prompt_three_way():
    def build(c):
        @c.command()
        def cli():
            pw = c.prompt("Password", hide_input=True)
            c.echo(f"got {pw}")

        return cli

    _assert_match(build, input="s3cret\n")
    body = (
        "@m.command()\n"
        "def cli():\n    pw = m.prompt('Password', hide_input=True)\n"
        "    m.echo(f'got {pw}')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, "s3cret\n")


def test_hidden_prompt_func_is_public():
    # click.termui.hidden_prompt_func exists and is what hidden prompts call.
    click = load_oracle()
    import clirelay.termui as mine

    assert hasattr(click.termui, "hidden_prompt_func")
    assert callable(mine.hidden_prompt_func)
    assert callable(mine.visible_prompt_func)


def test_password_option_three_way():
    def build(c):
        @c.command()
        @c.password_option()
        def cli(password):
            c.echo(f"pw={password}")

        return cli

    _assert_match(build, input="secret\nsecret\n")
    body = (
        "@m.command()\n@m.password_option()\n"
        "def cli(password):\n    m.echo(f'pw={password}')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, "secret\nsecret\n")


# --------------------------------------------------------------------------
# confirm / confirmation_option / confirmation_prompt, all three ways.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("answer", ["y", "n", "yes", "no"])
def test_confirm_three_way(answer):
    def build(c):
        @c.command()
        def cli():
            c.echo("yes!" if c.confirm("Continue?") else "no!")

        return cli

    _assert_match(build, input=answer + "\n")
    body = (
        "@m.command()\n"
        "def cli():\n    m.echo('yes!' if m.confirm('Continue?') else 'no!')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, answer + "\n")


def test_confirm_invalid_then_valid_three_way():
    def build(c):
        @c.command()
        def cli():
            c.echo("ok" if c.confirm("Go?") else "stop")

        return cli

    _assert_match(build, input="maybe\ny\n")
    body = (
        "@m.command()\n"
        "def cli():\n    m.echo('ok' if m.confirm('Go?') else 'stop')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, "maybe\ny\n")


@pytest.mark.parametrize("answer", ["y", "n"])
def test_confirmation_option_three_way(answer):
    def build(c):
        @c.command()
        @c.confirmation_option(prompt="Are you sure?")
        def cli():
            c.echo("done")

        return cli

    _assert_match(build, input=answer + "\n")
    body = (
        "@m.command()\n@m.confirmation_option(prompt='Are you sure?')\n"
        "def cli():\n    m.echo('done')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, answer + "\n")


def test_confirmation_prompt_mismatch_three_way():
    def build(c):
        @c.command()
        @c.option("--n", prompt=True, confirmation_prompt=True)
        def cli(n):
            c.echo(f"n={n}")

        return cli

    _assert_match(build, input="a\nb\nx\nx\n")
    body = (
        "@m.command()\n@m.option('--n', prompt=True, confirmation_prompt=True)\n"
        "def cli(n):\n    m.echo(f'n={n}')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, "a\nb\nx\nx\n")


def test_choice_prompt_reask_three_way():
    def build(c):
        @c.command()
        @c.option("--color", prompt=True, type=c.Choice(["r", "g"]))
        def cli(color):
            c.echo(f"color={color}")

        return cli

    _assert_match(build, input="x\nr\n")
    body = (
        "@m.command()\n@m.option('--color', prompt=True, type=m.Choice(['r','g']))\n"
        "def cli(color):\n    m.echo(f'color={color}')\n"
        "cli([], prog_name='cli')\n"
    )
    _three_way(body, "x\nr\n")


# --------------------------------------------------------------------------
# 3. ``multiple`` + list-splitting types read env vars split on os.pathsep.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("type_expr,value", [
    ("c.Path()", "a" + os.pathsep + "b"),
    ("c.Path()", "only"),
    ("None", "x" + os.pathsep + "y"),          # plain str does NOT pathsep-split
    ("c.STRING", "p q"),                         # str splits on whitespace
])
def test_multiple_envvar_split(type_expr, value):
    def build(c):
        ty = eval(type_expr)  # noqa: S307
        kwargs = {"multiple": True, "envvar": "P"}
        if ty is not None:
            kwargs["type"] = ty

        @c.command()
        @c.option("--p", **kwargs)
        def cli(p):
            c.echo(repr(p))

        return cli

    _assert_match(build, args=[], env={"P": value})


def test_multiple_file_envvar_split(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")

    def build(c):
        @c.command()
        @c.option("--p", multiple=True, type=c.File(), envvar="P")
        def cli(p):
            c.echo(repr(sorted(f.read() for f in p)))

        return cli

    val = str(tmp_path / "a.txt") + os.pathsep + str(tmp_path / "b.txt")
    _assert_match(build, args=[], env={"P": val})


# --------------------------------------------------------------------------
# 4. ``multiple=True`` with ``nargs`` yields a tuple of tuples.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["--kv", "a", "1", "--kv", "b", "2"],
    ["--kv", "x", "9"],
    [],
])
def test_multiple_nargs(args):
    def build(c):
        @c.command()
        @c.option("--kv", multiple=True, nargs=2)
        def cli(kv):
            c.echo(repr(kv))

        return cli

    _assert_match(build, args=args)


def test_multiple_nargs_typed():
    def build(c):
        @c.command()
        @c.option("--pt", multiple=True, nargs=2, type=int)
        def cli(pt):
            c.echo(repr(pt))

        return cli

    _assert_match(build, args=["--pt", "1", "2", "--pt", "3", "4"])


# --------------------------------------------------------------------------
# 6. DateTime message is singular with one format, plural otherwise.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("formats", [["%Y"], ["%Y", "%m"], ["%Y-%m-%d", "%H:%M"]])
def test_datetime_format_plurality(formats):
    def build(c):
        @c.command()
        @c.option("--d", type=c.DateTime(formats))
        def cli(d):
            c.echo(str(d))

        return cli

    _assert_match(build, args=["--d", "nope"])


# --------------------------------------------------------------------------
# 8. A ParamType subclass without a ``name`` uses its class name.
# --------------------------------------------------------------------------

def test_paramtype_without_name_info_dict():
    click = load_oracle()
    import clirelay

    def make(c):
        class NoName(c.ParamType):
            def convert(self, value, param, ctx):
                return value

        return NoName()

    assert make(click).to_info_dict() == make(clirelay).to_info_dict()
    assert make(clirelay).to_info_dict() == {"param_type": "NoName", "name": "NoName"}


# --------------------------------------------------------------------------
# 11. FloatRange with open bounds (value/clamp/metavar/message).
# --------------------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["--x", "0"], ["--x", "1"], ["--x", "0.5"], ["--help"],
])
def test_floatrange_open_bounds(args):
    def build(c):
        @c.command()
        @c.option("--x", type=c.FloatRange(min=0, max=1, min_open=True, max_open=True))
        def cli(x):
            c.echo(repr(x))

        return cli

    _assert_match(build, args=args)


@pytest.mark.parametrize("args", [["--x", "-5"], ["--x", "100"], ["--x", "3"]])
def test_floatrange_halfopen_clamp(args):
    def build(c):
        @c.command()
        @c.option("--x", type=c.FloatRange(min=0, max=10, clamp=True))
        def cli(x):
            c.echo(repr(x))

        return cli

    _assert_match(build, args=args)


# --------------------------------------------------------------------------
# 7. Context.with_resource: the resource __exit__ receives the exception that
#    the command raised; a clean run passes it None.
# --------------------------------------------------------------------------

def _with_resource_log(c, raise_it, mode):
    log = []

    class Res:
        def __enter__(self):
            log.append("enter")
            return 42

        def __exit__(self, exc_type, exc, tb):
            log.append(("exit", exc_type.__name__ if exc_type else None))
            return False

    @c.command()
    @c.pass_context
    def cli(ctx):
        ctx.with_resource(Res())
        if raise_it:
            raise RuntimeError("boom")
        c.echo("ok")

    if mode == "clirunner":
        c.testing.CliRunner().invoke(cli, [])
    else:  # standalone_mode=False
        try:
            cli.main([], standalone_mode=False)
        except (RuntimeError, SystemExit):
            pass
    return log


@pytest.mark.parametrize("raise_it", [False, True])
@pytest.mark.parametrize("mode", ["clirunner", "standalone"])
def test_with_resource_exception(raise_it, mode):
    click = load_oracle()
    import clirelay

    assert _with_resource_log(click, raise_it, mode) == _with_resource_log(
        clirelay, raise_it, mode
    )


# --------------------------------------------------------------------------
# 8b (info dict parity for a named custom type, for completeness).
# 9. Undecodable bytes in path errors render as the replacement character.
# --------------------------------------------------------------------------

def test_undecodable_path_bytes():
    load_oracle()
    bad = b"/nope\xff".decode("utf-8", "surrogateescape")
    body = (
        "@m.command()\n@m.argument('p', type=m.Path(exists=True))\n"
        "def cli(p):\n    m.echo('ok')\n"
        "cli([" + repr(bad) + "], prog_name='cli', standalone_mode=True)\n"
    )
    o_rc, o_out, o_err = _sub_io("click", ORACLE_DIR, body, b"")
    m_rc, m_out, m_err = _sub_io("clirelay", SRC, body, b"")
    assert o_rc == m_rc
    assert o_err.decode() == normalize(m_err.decode())
    assert "�" in o_err.decode()


# --------------------------------------------------------------------------
# 5 & 11. Completion resolves the argument at the cursor; ordering & no leak.
# --------------------------------------------------------------------------

def _complete(c, build, args, incomplete):
    import importlib

    name = c.__name__
    sc = importlib.import_module(name + ".shell_completion")
    cli = build(c)
    comp = sc.ShellComplete(cli, {}, "cli", "_CLI_COMPLETE")
    return [(i.value, i.type, i.help) for i in comp.get_completions(args, incomplete)]


def _assert_complete(build, args, incomplete):
    click = load_oracle()
    import clirelay

    assert _complete(click, build, args, incomplete) == _complete(
        clirelay, build, args, incomplete
    )


def _two_args(c):
    @c.command()
    @c.argument("src", type=c.Path())
    @c.argument("kind", type=c.Choice(["a", "b"]))
    def cli(src, kind):
        pass

    return cli


@pytest.mark.parametrize("args,incomplete", [
    ([], ""),
    (["x"], ""),
    (["x"], "a"),
    (["x", "a"], ""),
])
def test_completion_cursor_position(args, incomplete):
    _assert_complete(_two_args, args, incomplete)


def _nargs_args(c):
    @c.command()
    @c.argument("a", nargs=2, type=c.Choice(["x", "y"]))
    @c.argument("b", type=c.Choice(["m", "n"]))
    def cli(a, b):
        pass

    return cli


@pytest.mark.parametrize("given", [[], ["x"], ["x", "y"], ["x", "y", "m"]])
def test_completion_nargs_ordering(given):
    _assert_complete(_nargs_args, given, "")


def _variadic(c):
    @c.command()
    @c.argument("files", nargs=-1, type=c.Choice(["p", "q"]))
    def cli(files):
        pass

    return cli


@pytest.mark.parametrize("given", [[], ["p"], ["p", "q"]])
def test_completion_variadic_always_active(given):
    _assert_complete(_variadic, given, "")


def _nested(c):
    @c.group()
    @c.option("--opt", type=c.Choice(["1", "2"]))
    def cli(opt):
        pass

    @cli.command()
    @c.option("--sub", type=c.Choice(["a", "b"]))
    def run(sub):
        pass

    return cli


@pytest.mark.parametrize("args,incomplete", [
    ([], ""),
    (["--opt", "1", "run"], "--sub="),
    (["--opt", "1", "run"], "--"),
])
def test_completion_no_state_leak(args, incomplete):
    _assert_complete(_nested, args, incomplete)


# --------------------------------------------------------------------------
# 10. Group subclass hook call order over several scenarios.
# --------------------------------------------------------------------------

def _hook_log(c, scenario):
    import importlib

    log = []

    class LoggingGroup(c.Group):
        def get_command(self, ctx, name):
            log.append(("get_command", name))
            return super().get_command(ctx, name)

        def list_commands(self, ctx):
            log.append(("list_commands",))
            return super().list_commands(ctx)

        def resolve_command(self, ctx, args):
            log.append(("resolve_command", tuple(args)))
            return super().resolve_command(ctx, args)

        def make_context(self, info_name, args, parent=None, **extra):
            log.append(("make_context", info_name))
            return super().make_context(info_name, args, parent=parent, **extra)

        def parse_args(self, ctx, args):
            log.append(("parse_args", tuple(args)))
            return super().parse_args(ctx, args)

        def invoke(self, ctx):
            log.append(("invoke",))
            return super().invoke(ctx)

        def format_commands(self, ctx, formatter):
            log.append(("format_commands",))
            return super().format_commands(ctx, formatter)

        def shell_complete(self, ctx, incomplete):
            log.append(("shell_complete", incomplete))
            return super().shell_complete(ctx, incomplete)

    cli = LoggingGroup(name="cli")

    @cli.command()
    def run():
        c.echo("ran")

    if scenario in ("unknown", "missing", "help", "valid"):
        argmap = {"unknown": ["nope"], "missing": [], "help": ["--help"], "valid": ["run"]}
        c.testing.CliRunner().invoke(cli, argmap[scenario])
    else:  # completion
        sc = importlib.import_module(c.__name__ + ".shell_completion")
        comp = sc.ShellComplete(cli, {}, "cli", "_CLI_COMPLETE")
        comp.get_completions([] if scenario == "complete_empty" else ["run"], "")
    return log


@pytest.mark.parametrize("scenario", [
    "unknown", "missing", "help", "valid", "complete_empty", "complete_after",
])
def test_group_subclass_hooks(scenario):
    click = load_oracle()
    import clirelay

    assert _hook_log(click, scenario) == _hook_log(clirelay, scenario)
