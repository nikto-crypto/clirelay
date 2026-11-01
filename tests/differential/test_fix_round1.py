"""Differential tests for the behaviors found by the external evaluation.

Each item from "Fix round 1" is exercised here as a whole class of inputs, not
just the single reported example.  In-process cases run through ``run_both``;
width/encoding cases run as real subprocesses; the progress bar runs through a
pseudo-terminal.  Timing-dependent figures (ETA/speed) are the only thing
normalized away, and only in the progress-bar test, because the contract exempts
them.
"""
from __future__ import annotations

import io
import os
import re
import select
import stat
import subprocess
import sys

import pytest

import clirelay

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
# 1. Context.invoke / forward fill defaults (with conversion); passed values
#    are passed through unconverted.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("call", [
    "ctx.invoke(other)",
    "ctx.invoke(other, n='7')",
    "ctx.invoke(other, n=7)",
    "ctx.invoke(other, tags=('a','b'))",
    "ctx.forward(other)",
])
def test_ctx_invoke_defaults(call):
    def build(c):
        @c.group()
        def g():
            pass

        @g.command()
        @c.option("--n", type=int, default="15")
        @c.option("--tags", multiple=True)
        @c.option("--flag/--no-flag", default=True)
        def other(n, tags, flag):
            c.echo(f"{n!r} {tags!r} {flag!r}")

        @g.command()
        @c.pass_context
        def run(ctx):
            eval(call)  # noqa: S307 - fixed expressions above

        return g

    _assert_match(build, args=["run"])


def test_ctx_forward_passes_params():
    def build(c):
        @c.group()
        def g():
            pass

        @g.command()
        @c.option("--x", type=int, default=0)
        @c.option("--y", type=int, default="9")
        def dest(x, y):
            c.echo(f"{x!r} {y!r}")

        @g.command()
        @c.option("--x", type=int, default=3)
        @c.pass_context
        def src(ctx, x):
            ctx.forward(dest)

        return g

    _assert_match(build, args=["src", "--x", "5"])


# --------------------------------------------------------------------------
# 2. Prompts re-ask: empty input (no default), and callback rejection.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("inp", ["\nAnn\n", "\n\nBob\n", "Zoe\n"])
def test_prompt_empty_reask(inp):
    def build(c):
        @c.command()
        @c.option("--name", prompt=True)
        def cli(name):
            c.echo(f"got {name!r}")

        return cli

    _assert_match(build, args=[], input=inp)


@pytest.mark.parametrize("inp", ["no\nok\n", "bad\nnope\nok\n"])
def test_prompt_callback_reask(inp):
    def build(c):
        def cb(ctx, param, value):
            if value != "ok":
                raise c.BadParameter("must be ok")
            return value

        @c.command()
        @c.option("--v", prompt=True, callback=cb)
        def cli(v):
            c.echo(f"got {v!r}")

        return cli

    _assert_match(build, args=[], input=inp)


@pytest.mark.parametrize("inp", ["nan\n5\n", "7\n"])
def test_prompt_type_reask(inp):
    def build(c):
        @c.command()
        @c.option("--n", prompt=True, type=int)
        def cli(n):
            c.echo(f"got {n!r}")

        return cli

    _assert_match(build, args=[], input=inp)


def test_public_prompt_empty_reask():
    def build(c):
        @c.command()
        def cli():
            c.echo(f"got {c.prompt('Name')!r}")

        return cli

    _assert_match(build, args=[], input="\nBob\n")


# --------------------------------------------------------------------------
# 3. Feature switches: shared-destination flags, default on either side.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("args", [[], ["--upper"], ["--lower"]])
def test_feature_switch_default_first(args):
    def build(c):
        @c.command()
        @c.option("--upper", "t", flag_value="upper", default=True)
        @c.option("--lower", "t", flag_value="lower")
        def cli(t):
            c.echo(repr(t))

        return cli

    _assert_match(build, args=args)


@pytest.mark.parametrize("args", [[], ["--upper"], ["--lower"]])
def test_feature_switch_default_second(args):
    def build(c):
        @c.command()
        @c.option("--upper", "t", flag_value="upper")
        @c.option("--lower", "t", flag_value="lower", default=True)
        def cli(t):
            c.echo(repr(t))

        return cli

    _assert_match(build, args=args)


@pytest.mark.parametrize("args", [[], ["--x"]])
def test_lone_custom_flag_value(args):
    def build(c):
        @c.command()
        @c.option("--x", flag_value="v")
        def cli(x):
            c.echo(repr(x))

        return cli

    _assert_match(build, args=args)


# --------------------------------------------------------------------------
# 4. Optional-value options: is_flag=False with a flag_value.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("args", [[], ["--name"], ["--name", "x"], ["--name=y"]])
def test_optional_value_option(args):
    def build(c):
        @c.command()
        @c.option("--name", is_flag=False, flag_value="Flag", default="Default")
        def cli(name):
            c.echo(repr(name))

        return cli

    _assert_match(build, args=args)


@pytest.mark.parametrize("args", [[], ["--name"], ["--name", "x"]])
def test_optional_value_no_default(args):
    def build(c):
        @c.command()
        @c.option("--name", is_flag=False, flag_value="Flag")
        def cli(name):
            c.echo(repr(name))

        return cli

    _assert_match(build, args=args)


# --------------------------------------------------------------------------
# 5. Groups and "Missing command." vs. full help.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("naih", [True, False])
@pytest.mark.parametrize("iwc", [True, False])
@pytest.mark.parametrize("args", [[], ["--opt", "x"]])
def test_group_missing_command(naih, iwc, args):
    def build(c):
        @c.group(no_args_is_help=naih, invoke_without_command=iwc)
        @c.option("--opt")
        def g(opt):
            c.echo(f"ran {opt}")

        @g.command()
        def sub():
            pass

        return g

    _assert_match(build, args=args, prog_name="g")


# --------------------------------------------------------------------------
# 6. Default type inference falls back to str for odd defaults.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("default", [{"git"}, frozenset({"a"}), {"k": 1}, 3 + 0j])
def test_default_type_inference(default):
    def build(c):
        @c.command()
        @c.option("--tag", default=default)
        def cli(tag):
            c.echo(f"{tag!r} {type(tag).__name__}")

        return cli

    _assert_match(build, args=[])


# --------------------------------------------------------------------------
# 7. Help text details.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("required,nargs", [
    (True, 1), (False, 1), (True, 2), (False, 2), (False, -1),
])
def test_choice_argument_metavar(required, nargs):
    def build(c):
        @c.command()
        @c.argument("x", type=c.Choice(["a", "b"]), required=required, nargs=nargs)
        def cli(x):
            pass

        return cli

    _assert_match(build, args=["--help"], terminal_width=80)


@pytest.mark.parametrize("default", ["", "hi", 0, False])
def test_empty_default_shown(default):
    def build(c):
        @c.command()
        @c.option("--x", default=default, show_default=True)
        def cli(x):
            pass

        return cli

    _assert_match(build, args=["--help"], terminal_width=80)


@pytest.mark.parametrize("width", [40, 60, 80])
def test_option_help_backspace_and_hyphens(width):
    def build(c):
        @c.command()
        @c.option("--x", help="first line\n\b\nkeep one\nkeep two")
        @c.option(
            "--cors",
            help="Enable CORS by serving the Access-Control-Allow-Origin "
            "header to every client.",
        )
        def cli(x, cors):
            pass

        return cli

    _assert_match(build, args=["--help"], terminal_width=width)


@pytest.mark.parametrize("width", [40, 60, 80, 120])
def test_command_help_hyphen_wrap(width):
    def build(c):
        @c.command(
            help="Serve the Access-Control-Allow-Origin header to every "
            "client that connects over a long-lived keep-alive connection."
        )
        def cli():
            pass

        return cli

    _assert_match(build, args=["--help"], terminal_width=width)


def test_backslash_b_block_indent():
    def build(c):
        @c.command(help="Intro.\n\n\b\n  indented line\n    more indented")
        def cli():
            pass

        return cli

    _assert_match(build, args=["--help"], terminal_width=80)


# --------------------------------------------------------------------------
# 8 & 10. Real-subprocess behavior: COLUMNS width and non-UTF-8 stdout.
# --------------------------------------------------------------------------

def _run_subprocess(mod: str, root: str, body: str, env: dict) -> subprocess.CompletedProcess:
    code = (
        f"import sys; sys.path.insert(0, {root!r}); import {mod} as m\n{body}\n"
    )
    full_env = dict(os.environ)
    full_env.pop("NO_COLOR", None)
    full_env.update(env)
    return subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        env=full_env,
    )


@pytest.mark.parametrize("columns", ["40", "50", "60", "80", "120"])
def test_subprocess_columns_width(columns):
    load_oracle()
    body = (
        "@m.command()\n"
        "@m.option('--cors', help='Enable CORS by serving the "
        "Access-Control-Allow-Origin header to every client that asks.')\n"
        "def cli(cors):\n    pass\n"
        "cli(['--help'], prog_name='cli', standalone_mode=False)\n"
    )
    env = {"COLUMNS": columns, "TERM": "dumb"}
    o = _run_subprocess("click", ORACLE_DIR, body, env)
    me = _run_subprocess("clirelay", SRC, body, env)
    assert o.returncode == me.returncode
    assert o.stdout.decode() == normalize(me.stdout.decode())


@pytest.mark.parametrize("text", ["café", "naïve", "Ω≈ç", "ascii only"])
def test_subprocess_ascii_stdout(text):
    load_oracle()
    body = f"m.echo({text!r})"
    env = {"PYTHONIOENCODING": "ascii"}
    o = _run_subprocess("click", ORACLE_DIR, body, env)
    me = _run_subprocess("clirelay", SRC, body, env)
    assert o.returncode == me.returncode == 0
    assert o.stdout == me.stdout


# --------------------------------------------------------------------------
# 9. Progress bar renders on a terminal (minus timing figures).
# --------------------------------------------------------------------------

_TIME_RE = re.compile(r"\d{1,2}:\d{2}:\d{2}")


def _run_pty(mod: str, root: str, body: str) -> bytes:
    import pty

    code = (
        f"import sys; sys.path.insert(0, {root!r}); import {mod} as m\n{body}\n"
    )
    env = dict(os.environ, COLUMNS="80", LINES="24", TERM="xterm")
    env.pop("NO_COLOR", None)
    pid, fd = pty.fork()
    if pid == 0:
        os.environ.update(env)
        try:
            os.execv(sys.executable, [sys.executable, "-I", "-c", code])
        finally:
            os._exit(127)
    out = b""
    while True:
        r, _, _ = select.select([fd], [], [], 3.0)
        if not r:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    try:
        os.close(fd)
    except OSError:
        pass
    os.waitpid(pid, 0)
    return out


PBAR_BODIES = {
    "basic": (
        "with m.progressbar([1,2,3,4], label='work') as bar:\n"
        "    for _ in bar: pass\n"
    ),
    "pos": (
        "with m.progressbar(length=4, label='dl', show_percent=True, "
        "show_pos=True) as bar:\n"
        "    for _ in range(4): bar.update(1)\n"
    ),
    "item": (
        "with m.progressbar([10,20,30], label='x', "
        "item_show_func=lambda i: f'item {i}' if i else None) as bar:\n"
        "    for _ in bar: pass\n"
    ),
    "empty": (
        "with m.progressbar([], label='none') as bar:\n"
        "    for _ in bar: pass\n"
    ),
}


@pytest.mark.parametrize("kind", list(PBAR_BODIES))
def test_progressbar_pty(kind):
    load_oracle()
    body = PBAR_BODIES[kind]
    o = _run_pty("click", ORACLE_DIR, body).decode("utf-8", "replace")
    me = _run_pty("clirelay", SRC, body).decode("utf-8", "replace")
    # Timing figures (ETA) are exempt; strip any HH:MM:SS tokens before compare.
    assert _TIME_RE.sub("T", o) == _TIME_RE.sub("T", normalize(me))


# --------------------------------------------------------------------------
# 11. version_option package auto-detection (decoration-time guess).
# --------------------------------------------------------------------------

def test_version_option_main(tmp_path):
    # Defined in __main__ with no package -> cannot determine.
    def build(c):
        @c.command()
        @c.version_option()
        def cli():
            pass

        return cli

    _assert_match(build, args=["--version"], prog_name="tool")


def test_version_option_top_level_module(tmp_path):
    """A top-level module (no package) guesses its own name as the distribution."""
    import importlib

    click = load_oracle()
    (tmp_path / "toplvl_tool.py").write_text(
        "def build(mod):\n"
        "    @mod.command()\n"
        "    @mod.version_option()\n"
        "    def cli():\n        pass\n"
        "    return cli\n"
    )
    from .harness import _invoke

    sys.path.insert(0, str(tmp_path))
    try:
        mod = importlib.import_module("toplvl_tool")
        importlib.reload(mod)
        o = _invoke(click, mod.build(click), ["--version"], None, None,
                    "tool", False, True)
        m = _invoke(clirelay, mod.build(clirelay), ["--version"], None, None,
                    "tool", False, True)
        assert o["exit_code"] == m["exit_code"]
        assert o["exception"] == (
            tuple(normalize(x) for x in m["exception"]) if m["exception"] else None
        )
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("toplvl_tool", None)


# --------------------------------------------------------------------------
# 12. Shell completion.
# --------------------------------------------------------------------------

def _complete(mod, cli, args, incomplete):
    import importlib

    sc = importlib.import_module(mod.__name__ + ".shell_completion")
    comp = sc.BashComplete(cli, {}, "cli", "_CLI_COMPLETE")
    return [(i.type, i.value) for i in comp.get_completions(list(args), incomplete)]


def _assert_complete(builder, args, incomplete):
    click = load_oracle()
    o = _complete(click, builder(click), args, incomplete)
    m = _complete(clirelay, builder(clirelay), args, incomplete)
    assert o == m, f"oracle={o} mine={m}"


@pytest.mark.parametrize("args,inc", [
    ([], "--"),
    (["--foo", "x"], "--"),
    (["--tag", "x"], "--"),
    (["--foo", "x", "--tag", "y"], "--"),
    (["-v"], "--"),
])
def test_completion_used_options(args, inc):
    def build(c):
        @c.command()
        @c.option("--foo")
        @c.option("--bar")
        @c.option("--tag", multiple=True)
        @c.option("-v", "--verbose", count=True)
        def cli(foo, bar, tag, verbose):
            pass

        return cli

    _assert_complete(build, args, inc)


@pytest.mark.parametrize("kind", ["path", "file", "dir", "filew"])
def test_completion_path_file(kind):
    def build(c):
        if kind == "path":
            ty = c.Path()
        elif kind == "file":
            ty = c.File("r")
        elif kind == "filew":
            ty = c.File("w")
        else:
            ty = c.Path(file_okay=False, dir_okay=True)

        @c.command()
        @c.argument("p", type=ty)
        def cli(p):
            pass

        return cli

    _assert_complete(build, [], "")


@pytest.mark.parametrize("args", [["--pair"], ["--pair", "a"], ["--pair", "a", "b"]])
def test_completion_nargs(args):
    def build(c):
        @c.command()
        @c.option("--pair", nargs=2, type=c.Choice(["a", "b", "c"]))
        def cli(pair):
            pass

        return cli

    _assert_complete(build, args, "")


@pytest.mark.parametrize("inc", ["", "a", "b", "z"])
def test_completion_custom_group(inc):
    def build(c):
        class Lazy(c.Group):
            def list_commands(self, ctx):
                return ["alpha", "beta"]

            def get_command(self, ctx, name):
                if name in ("alpha", "beta"):
                    @c.command(name=name)
                    def _cmd():
                        pass

                    return _cmd
                return None

        return Lazy(name="g")

    _assert_complete(build, [], inc)


# --------------------------------------------------------------------------
# 13. to_info_dict for commands, groups and context (several shapes).
# --------------------------------------------------------------------------

def _info_norm(obj):
    import json

    text = normalize(json.dumps(obj, default=repr, sort_keys=True))
    return text.replace('"_click_default_help"', '"help"')


@pytest.mark.parametrize("shape", ["flat", "nested", "chain"])
def test_to_info_dict_shapes(shape):
    click = load_oracle()

    def make(c):
        if shape == "flat":
            @c.command()
            @c.option("--x", type=int, default=1)
            @c.argument("y")
            def cli(x, y):
                pass

            return cli

        @c.group(chain=(shape == "chain"))
        def cli():
            pass

        @cli.command()
        @c.option("--a")
        def one(a):
            pass

        @cli.command()
        def two():
            pass

        if shape == "nested":
            @cli.group()
            def sub():
                pass

            @sub.command()
            def leaf():
                pass

        return cli

    oc = make(click)
    mc = make(clirelay)
    octx = click.Context(oc, info_name="cli")
    mctx = clirelay.Context(mc, info_name="cli")
    assert _info_norm(oc.to_info_dict(octx)) == _info_norm(mc.to_info_dict(mctx))


# --------------------------------------------------------------------------
# 14. Ordering: eager callbacks and help option names.
# --------------------------------------------------------------------------

def test_eager_callback_order():
    click = load_oracle()

    def run(c):
        order = []

        def mk(n):
            def cb(ctx, param, value):
                order.append(n)

            return cb

        @c.command()
        @c.option("--a", is_flag=True, is_eager=True, expose_value=False, callback=mk("a"))
        @c.option("--b", is_flag=True, is_eager=True, expose_value=False, callback=mk("b"))
        @c.option("--c", is_flag=True, is_eager=True, expose_value=False, callback=mk("c"))
        def cli():
            pass

        import importlib

        testing = importlib.import_module(c.__name__ + ".testing")
        testing.CliRunner().invoke(cli, ["--a", "--b", "--c"])
        return order

    assert run(click) == run(clirelay)


@pytest.mark.parametrize("names", [["-h", "--help"], ["--help", "-h"], ["--helpme"]])
def test_help_option_names_order(names):
    click = load_oracle()

    def get(c):
        @c.command(context_settings={"help_option_names": names})
        def cli():
            pass

        ctx = cli.make_context("cli", [], resilient_parsing=True)
        return cli.get_help_option_names(ctx)

    assert get(click) == get(clirelay)


# --------------------------------------------------------------------------
# Realistic apps exercising ctx.invoke/forward, optional values, prompts,
# feature switches and completion together.
# --------------------------------------------------------------------------

def _dbctl(c):
    """A database-style CLI: feature switches, optional values, delegation."""

    @c.group()
    @c.option("--verbose/--quiet", default=False)
    @c.pass_context
    def cli(ctx, verbose):
        ctx.obj = {"verbose": verbose}

    @cli.command()
    @c.option("--format", "fmt", flag_value="json", default=True)
    @c.option("--yaml", "fmt", flag_value="yaml")
    @c.option("--limit", type=int, default="100")
    def query(fmt, limit):
        c.echo(f"query fmt={fmt} limit={limit!r}")

    @cli.command()
    @c.option("--page", is_flag=False, flag_value="1", default="all")
    @c.pass_context
    def dump(ctx, page):
        c.echo(f"dump page={page!r}")
        ctx.invoke(query)

    return cli


@pytest.mark.parametrize("args", [
    ["query"], ["query", "--yaml"], ["query", "--limit", "5"],
    ["dump"], ["dump", "--page"], ["dump", "--page", "3"], [],
])
def test_dbctl_app(args):
    _assert_match(_dbctl, args=args)


def _weblaunch(c):
    """A web-server launcher: COLUMNS-sensitive help, optional values."""

    @c.command(help="Launch the development web server with the chosen options.")
    @c.option(
        "--cors",
        help="Enable CORS by serving the Access-Control-Allow-Origin header to "
        "every client that connects.",
    )
    @c.option("--reload", is_flag=False, flag_value="auto", default="off")
    @c.argument("host", type=c.Choice(["localhost", "0.0.0.0"]), required=False)
    def cli(cors, reload, host):
        c.echo(f"serve cors={cors!r} reload={reload!r} host={host!r}")

    return cli


@pytest.mark.parametrize("args", [
    [], ["--reload"], ["--reload", "fast"], ["localhost"], ["--help"],
])
def test_weblaunch_app(args):
    _assert_match(_weblaunch, args=args, terminal_width=80)


def _taskqueue(c):
    """A task-queue CLI: prompts that re-ask, delegation via forward."""

    @c.group()
    def cli():
        pass

    @cli.command()
    @c.option("--name", prompt=True)
    @c.option("--priority", type=int, prompt=True, default=5)
    def add(name, priority):
        c.echo(f"added {name!r} p={priority}")

    @cli.command()
    @c.option("--name", prompt=True)
    @c.option("--priority", type=int, default=1)
    @c.pass_context
    def urgent(ctx, name, priority):
        ctx.forward(add)

    return cli


@pytest.mark.parametrize("args,inp", [
    (["add"], "build\n9\n"),
    (["add"], "\nship\n\n"),
    (["urgent"], "deploy\n"),
])
def test_taskqueue_app(args, inp):
    _assert_match(_taskqueue, args=args, input=inp)
