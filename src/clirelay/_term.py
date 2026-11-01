"""Terminal-only machinery: pager, editor, progress bar, raw input.

These are refined and verified through a PTY in a later phase; the structure here
is enough for the rest of the library to import and for non-interactive paths.
"""
from __future__ import annotations

import contextlib
import os
import sys
import time
import typing as t

from .utils import echo


# -- pager ------------------------------------------------------------------

@contextlib.contextmanager
def get_pager_file(color: bool | None = None) -> t.Iterator[t.TextIO]:
    import io

    buffer = io.StringIO()
    try:
        yield buffer  # type: ignore[misc]
    finally:
        pager([buffer.getvalue()], color)


def pager(generator: t.Iterable[str], color: bool | None = None) -> None:
    text = "".join(generator)
    if not _isatty():
        echo(text, color=color)
        return
    cmd = os.environ.get("PAGER") or "less"
    _pipe_to_pager(cmd, f"{text}\n", color)


def _pipe_to_pager(cmd: str, text: str, color: bool | None) -> None:
    import subprocess

    from ._ansi import strip_ansi

    if color is None or not color:
        text = strip_ansi(text)
    env = dict(os.environ)
    if "LESS" not in env:
        env["LESS"] = "-R"
    proc = subprocess.Popen(
        cmd, shell=True, stdin=subprocess.PIPE, env=env
    )
    try:
        proc.communicate(text.encode("utf-8", "replace"))
    except (OSError, KeyboardInterrupt):
        pass


def _isatty() -> bool:
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


# -- editor -----------------------------------------------------------------

class Editor:
    def __init__(
        self,
        editor: str | None = None,
        env: t.Mapping[str, str] | None = None,
        require_save: bool = True,
        extension: str = ".txt",
    ) -> None:
        self.editor = editor
        self.env = env
        self.require_save = require_save
        self.extension = extension

    def get_editor(self) -> str:
        if self.editor is not None:
            return self.editor
        for key in ("VISUAL", "EDITOR"):
            rv = os.environ.get(key)
            if rv:
                return rv
        for ed in ("sensible-editor", "vim", "nano"):
            return ed
        return "vi"

    def edit_files(self, filenames: t.Iterable[str]) -> None:
        import subprocess

        editor = self.get_editor()
        environ = dict(os.environ)
        if self.env:
            environ.update(self.env)
        quoted = " ".join(f'"{fn}"' for fn in filenames)
        proc = subprocess.Popen(
            f"{editor} {quoted}", env=environ, shell=True
        )
        ret = proc.wait()
        if ret != 0:
            from .exceptions import ClickException

            raise ClickException(f"{editor}: Editing failed")

    def edit(self, text: t.Any) -> t.Any:
        import tempfile

        binary = isinstance(text, (bytes, bytearray))
        if text is None:
            data: bytes = b""
        elif binary:
            data = bytes(text)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            data = text.encode("utf-8-sig")

        fd, name = tempfile.mkstemp(suffix=self.extension, prefix="editor-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            before = os.path.getmtime(name)
            self.edit_files([name])
            after = os.path.getmtime(name)
            if self.require_save and before == after:
                return None
            with open(name, "rb") as f:
                rv = f.read()
            if binary:
                return rv
            return rv.decode("utf-8-sig").replace("\r\n", "\n")
        finally:
            os.unlink(name)


def open_url(url: str, wait: bool = False, locate: bool = False) -> int:
    import subprocess

    if sys.platform == "darwin":
        args = ["open"]
        if wait:
            args.append("-W")
        if locate:
            args.append("-R")
        args.append(url)
        try:
            return subprocess.Popen(args).wait() if wait else (subprocess.Popen(args) and 0)
        except OSError:
            return 1
    try:
        import webbrowser

        webbrowser.open(url)
        return 0
    except Exception:
        return 1


# -- raw input --------------------------------------------------------------

@contextlib.contextmanager
def raw_terminal() -> t.Iterator[int]:
    import termios
    import tty

    if not sys.stdin.isatty():
        f: t.Any = open("/dev/tty")
        fd = f.fileno()
    else:
        fd = sys.stdin.fileno()
        f = None
    try:
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            yield fd
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            sys.stdout.flush()
    finally:
        if f is not None:
            f.close()


def getchar(echo_char: bool = False) -> str:
    with raw_terminal() as fd:
        ch = os.read(fd, 32).decode(sys.stdin.encoding or "utf-8", "replace")
    if echo_char:
        echo(ch, nl=False)
    if ch == "\x03":
        raise KeyboardInterrupt()
    if ch == "\x04":
        raise EOFError()
    return ch


def pause(info: str | None = None, err: bool = False) -> None:
    if info is None:
        info = "Press any key to continue..."
    if not _isatty():
        return
    try:
        if info:
            echo(info, nl=False, err=err)
        getchar()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        if info:
            echo(err=err)


# -- progress bar -----------------------------------------------------------

class ProgressBar:
    def __init__(
        self,
        iterable: t.Iterable[t.Any] | None,
        length: int | None = None,
        fill_char: str = "#",
        empty_char: str = " ",
        bar_template: str = "%(bar)s",
        info_sep: str = "  ",
        hidden: bool = False,
        show_eta: bool = True,
        show_percent: bool | None = None,
        show_pos: bool = False,
        item_show_func: t.Callable[..., str | None] | None = None,
        label: str | None = None,
        file: t.TextIO | None = None,
        color: bool | None = None,
        update_min_steps: int = 1,
        width: int = 30,
    ) -> None:
        self.fill_char = fill_char
        self.empty_char = empty_char
        self.bar_template = bar_template
        self.info_sep = info_sep
        self.hidden = hidden
        self.show_eta = show_eta
        self.show_percent = show_percent
        self.show_pos = show_pos
        self.item_show_func = item_show_func
        self.label = label or ""
        if file is None:
            file = sys.stdout
        self.file = file
        self.color = color
        self.update_min_steps = update_min_steps
        self.width = width

        if length is None and iterable is not None:
            try:
                length = len(iterable)  # type: ignore[arg-type]
            except TypeError:
                length = None
        if iterable is None:
            if length is None:
                raise TypeError("iterable or length is required")
            iterable = range(length)
        self.iter = iter(iterable)
        self.length = length
        self.pos = 0
        self.finished = False
        self.current_item: t.Any = None
        self.entered = False
        try:
            self.is_hidden = hidden or not self.file.isatty()
        except Exception:
            self.is_hidden = True
        self._label_shown = False

        # Rendering state: the last line drawn (for de-duplicating identical
        # frames) and the widest line so far (for erasing a now-shorter line).
        self._last_line: str | None = None
        self.max_width = 0
        # Timing state (used only for the exempt ETA/speed figures).
        self.start = self.last_eta = time.time()
        self._last_tick = self.start
        self.avg: list[float] = []

    def __enter__(self) -> ProgressBar:
        self.entered = True
        self.render_progress()
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.render_finish()

    def __iter__(self) -> t.Iterator[t.Any]:
        if not self.entered:
            raise RuntimeError("You need to use progress bars in a with block.")
        self.render_progress()
        return self.generator()

    def __next__(self) -> t.Any:
        return next(iter(self))

    def generator(self) -> t.Iterator[t.Any]:
        if not self.entered:
            raise RuntimeError("You need to use progress bars in a with block.")
        if self.hidden:
            yield from self.iter
            return
        for item in self.iter:
            self.current_item = item
            # Draw once the item is known (so item_show_func takes effect) and
            # again after advancing; identical frames collapse via de-dup.
            self.render_progress()
            yield item
            self.update(1)
        self.finish()
        self.render_progress()

    def update(self, n_steps: int, current_item: t.Any = None) -> None:
        if current_item is not None:
            self.current_item = current_item
        now = time.time()
        if n_steps > 0:
            self.avg = (self.avg + [(now - self._last_tick) / n_steps])[-7:]
        self._last_tick = now
        self.pos += n_steps
        self.render_progress()

    def finish(self) -> None:
        self.finished = True
        self.current_item = None

    # -- figures ------------------------------------------------------------

    @property
    def pct(self) -> float:
        if self.finished:
            return 1.0
        if not self.length:
            return 0.0
        return min(self.pos / self.length, 1.0)

    @property
    def time_per_iteration(self) -> float:
        if not self.avg:
            return 0.0
        return sum(self.avg) / len(self.avg)

    @property
    def eta(self) -> float:
        if self.length is not None and not self.finished:
            return self.time_per_iteration * (self.length - self.pos)
        return 0.0

    @property
    def eta_known(self) -> bool:
        # The ETA appears only once the task has been running long enough to
        # estimate it; its value is timing-dependent and exempt from parity.
        return (
            self.show_eta
            and self.length is not None
            and not self.finished
            and bool(self.avg)
            and (time.time() - self.start) >= 1.0
        )

    def format_eta(self) -> str:
        if not self.eta_known:
            return ""
        seconds = int(self.eta)
        s = seconds % 60
        seconds //= 60
        m = seconds % 60
        seconds //= 60
        h = seconds % 24
        days = seconds // 24
        if days:
            return f"{days}d {h:02}:{m:02}:{s:02}"
        return f"{h:02}:{m:02}:{s:02}"

    def format_pos(self) -> str:
        pos = str(self.pos)
        if self.length is not None:
            pos += f"/{self.length}"
        return pos

    def format_pct(self) -> str:
        return f"{int(self.pct * 100):3d}%"

    def format_bar(self) -> str:
        if self.length is not None:
            filled = int(self.pct * self.width)
            bar = self.fill_char * filled
            bar += self.empty_char * (self.width - filled)
        elif self.finished:
            bar = self.fill_char * self.width
        else:
            # Indeterminate: a block that moves with position (its motion is
            # timing/position-dependent and exempt from exact parity).
            bar = list(self.empty_char * self.width)
            idx = int(self.pos) % (self.width or 1)
            bar[idx] = self.fill_char
            bar = "".join(bar)
        return bar

    def format_progress_line(self) -> str:
        info_bits: list[str] = []
        show_pct = (
            self.show_percent
            if self.show_percent is not None
            else self.length is not None
        )
        if self.show_pos:
            info_bits.append(self.format_pos())
        if show_pct:
            info_bits.append(self.format_pct())
        eta = self.format_eta()
        if eta:
            info_bits.append(eta)
        if self.item_show_func is not None and not self.finished:
            item_info = self.item_show_func(self.current_item)
            if item_info is not None:
                info_bits.append(item_info)

        return self.bar_template % {
            "label": self.label,
            "bar": self.format_bar(),
            "info": self.info_sep.join(info_bits),
        }

    # -- drawing ------------------------------------------------------------

    def render_progress(self) -> None:
        from ._wrap import term_len

        if self.is_hidden:
            # On a non-terminal, only the label line is emitted (once); the live
            # bar is not drawn.
            if not self._label_shown:
                echo(self.label, file=self.file, color=self.color)
                self._label_shown = True
            return

        line = self.format_progress_line()
        line_len = term_len(line)
        if line_len < self.max_width:
            # Pad to erase whatever the previous, longer frame left behind.
            line = line + " " * (self.max_width - line_len)
        else:
            self.max_width = line_len

        if line == self._last_line:
            return  # identical frame: nothing to redraw
        self._last_line = line

        self.file.write(f"\r\x1b[?25l{line}")
        self.file.flush()

    def render_finish(self) -> None:
        if self.is_hidden:
            return
        # Show the cursor again and end the line.
        self.file.write("\x1b[?25h\n")
        self.file.flush()
