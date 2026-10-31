"""Differential tests for terminal-only behavior.

``edit`` is driven by an ``EDITOR`` script.  ``echo_via_pager`` and ``getchar``
are driven inside a pseudo-terminal so their tty-only paths run; ``PAGER`` points
at a logging script.  Each oracle run happens in its own subprocess so its import
stays isolated, and only observable results are compared.
"""
from __future__ import annotations

import os
import select
import stat
import subprocess
import sys
import textwrap

import pytest

import clirelay

from ._oracle import ORACLE_DIR, load_oracle
from .normalize import normalize

SRC = os.path.abspath("src")


def _write_script(path: str, body: str) -> str:
    with open(path, "w") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IRWXU)
    return path


def _run_in_pty(mod: str, path: str, body: str, feed: bytes = b"") -> str:
    """Run `import <mod> as m; <body>` with a pty as stdio; feed input; capture."""
    import pty

    code = (
        f"import sys; sys.path.insert(0, {path!r}); sys.path.insert(0, {SRC!r}); "
        f"import {mod} as m\n{body}\n"
    )
    pid, fd = pty.fork()
    if pid == 0:  # child
        try:
            os.execv(sys.executable, [sys.executable, "-I", "-c", code])
        finally:
            os._exit(127)
    if feed:
        os.write(fd, feed)
    out = b""
    deadline_reads = 0
    while deadline_reads < 50:
        r, _, _ = select.select([fd], [], [], 2.0)
        if not r:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        deadline_reads += 1
    try:
        os.close(fd)
    except OSError:
        pass
    os.waitpid(pid, 0)
    return out.decode("utf-8", "replace")


# -- edit -------------------------------------------------------------------

def test_edit_via_editor(tmp_path, monkeypatch):
    load_oracle()
    editor = _write_script(
        str(tmp_path / "ed.sh"), "#!/bin/sh\nprintf ' EDITED\\n' >> \"$1\"\n"
    )
    monkeypatch.setenv("EDITOR", editor)
    monkeypatch.setenv("VISUAL", editor)

    mine = clirelay.edit("hello")
    oracle = _oracle_edit("hello", editor)
    assert normalize(mine) == oracle


def _oracle_edit(text: str, editor: str) -> str:
    code = textwrap.dedent(
        f"""
        import os, sys
        sys.path.insert(0, {ORACLE_DIR!r})
        os.environ["EDITOR"] = {editor!r}
        os.environ["VISUAL"] = {editor!r}
        import click
        sys.stdout.write(repr(click.edit({text!r})))
        """
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True
    )
    return eval(out.stdout)  # noqa: S307


# -- pager through a pty + logging script -----------------------------------

@pytest.mark.parametrize("text", ["line one\nline two\nline three\n", "short"])
def test_pager_pty(tmp_path, text):
    load_oracle()
    mine_log = tmp_path / "mine.log"
    oracle_log = tmp_path / "oracle.log"

    def run(mod, path, log):
        pager = _write_script(
            str(tmp_path / f"pg_{mod}.sh"), f'#!/bin/sh\ncat >> "{log}"\n'
        )
        body = (
            f"import os; os.environ['PAGER'] = {pager!r}; "
            f"m.echo_via_pager({text!r})"
        )
        _run_in_pty(mod, path, body)
        return log.read_text() if log.exists() else ""

    mine = run("clirelay", SRC, mine_log)
    oracle = run("click", ORACLE_DIR, oracle_log)
    assert oracle == normalize(mine)


# -- getchar through a pty --------------------------------------------------

@pytest.mark.parametrize("feed", [b"a", b"Z", b"1"])
def test_getchar_pty(feed):
    load_oracle()
    body = "c = m.getchar(); import sys; sys.stdout.write('GOT:' + c); sys.stdout.flush()"
    mine = _extract(_run_in_pty("clirelay", SRC, body, feed))
    oracle = _extract(_run_in_pty("click", ORACLE_DIR, body, feed))
    assert oracle == normalize(mine)


def _extract(text: str) -> str:
    marker = "GOT:"
    if marker in text:
        return text[text.index(marker) + len(marker):][:1]
    return f"<no marker: {text!r}>"
