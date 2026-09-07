"""Textual fullscreen frontend for the shared Sbaitso engine."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, RichLog

from .engine import Engine, EngineArgs, Inputs
from .events import Bell, Beep, Clear, Event, KeyclickMode, Line, Palette, Prompt, Quit, Say
from .layout import RESPONSE_INDENT, SAY_WRAP_WIDTH, wrap_terminal_line

# Rich equivalents of the native renderer's ANSI palette semantics.
LINE_STYLE = {"white": "white", "cyan": "cyan", "yellow": "yellow", "green": "green", "red": "red", "dim": "dim"}
PALETTE_STYLE = {"cga1": "cyan", "cga2": "green", "ega": "white", "vga": "white", "amber": "yellow"}


class SbaitsoApp(App[None]):
    """A DOS-styled Textual adapter using the same layout rules as native mode."""

    CSS = """
    Screen { background: #0a0a0a; color: #c8c8c8; }
    #terminal { height: 1fr; }
    #entry { dock: bottom; }
    Screen.vga, Screen.vga #terminal, Screen.vga #entry { background: #0a0a0a; color: #c8c8c8; border: solid #c8c8c8; }
    Screen.cga1, Screen.cga1 #terminal, Screen.cga1 #entry { background: #0000aa; color: #55ffff; border: solid #55ffff; }
    Screen.cga2, Screen.cga2 #terminal, Screen.cga2 #entry { background: #000000; color: #55ff55; border: solid #55ff55; }
    Screen.ega, Screen.ega #terminal, Screen.ega #entry { background: #000055; color: #ffffff; border: solid #ffffff; }
    Screen.amber, Screen.amber #terminal, Screen.amber #entry { background: #160400; color: #ffb347; border: solid #ffb347; }
    """

    def __init__(self, args: EngineArgs) -> None:
        super().__init__()
        self.engine = Engine.from_args(args)
        self.inputs = Inputs()
        self._runner: asyncio.Task[None] | None = None
        self._prompt_label = "YOU"
        self._say_word = ""
        self._say_column = 0
        self._response_started = False
        self._palette = args.palette
        self._say_style = PALETTE_STYLE.get(self._palette, "white")
        self._chunks: list[tuple[str, str]] = []
        self._waiting = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield RichLog(id="terminal", wrap=True, highlight=False, markup=False)
            yield Input(placeholder="YOU> ", id="entry")

    def on_mount(self) -> None:
        self.screen.add_class(self._palette)
        self._runner = asyncio.create_task(self._run_engine())
        self.query_one(Input).focus()

    async def _run_engine(self) -> None:
        async for event in self.engine.run(self.inputs):
            await self.render_event(event)
            if isinstance(event, Quit):
                self.exit()
                return

    def _append(self, text: str, style: str = "white") -> None:
        if text:
            self._chunks.append((text, style))

    def _render_terminal(self) -> None:
        document = Text()
        for text, style in self._chunks:
            document.append(text, style=style)
        if self._waiting:
            document.append("\n REQUEST SENT — WAITING FOR RESPONSE...", style="yellow")
        terminal = self.query_one("#terminal", RichLog)
        terminal.clear()
        terminal.write(document, scroll_end=True)

    def _reset_response(self) -> None:
        self._say_word = ""
        self._say_column = 0
        self._response_started = False

    def _ensure_response_indent(self) -> None:
        if self._say_column == 0:
            self._append(RESPONSE_INDENT, self._say_style)
            self._say_column = len(RESPONSE_INDENT)

    def _end_response_line(self) -> None:
        if self._say_column:
            self._append("\n", self._say_style)
            self._say_column = 0

    async def _write_response_char(self, char: str, reveal: bool) -> None:
        self._ensure_response_indent()
        self._append(char, self._say_style)
        self._say_column += 1
        self._response_started = True
        self._render_terminal()
        if reveal and not self.engine.settings.fast:
            await asyncio.sleep(0.012)

    async def _flush_say_word(self, reveal: bool) -> None:
        if not self._say_word:
            return
        if self._say_column and self._say_column + len(self._say_word) > SAY_WRAP_WIDTH:
            self._end_response_line()
        self._ensure_response_indent()
        for char in self._say_word:
            if self._say_column >= SAY_WRAP_WIDTH:
                self._end_response_line()
            await self._write_response_char(char, reveal)
        self._say_word = ""

    async def _write_say_text(self, text: str, reveal: bool) -> None:
        """Match native buffered, word-boundary response wrapping."""
        for char in text:
            if char == "\n":
                await self._flush_say_word(reveal)
                self._end_response_line()
            elif char.isspace():
                await self._flush_say_word(reveal)
                if self._say_column < SAY_WRAP_WIDTH:
                    await self._write_response_char(char, reveal)
            else:
                self._say_word += char

    async def render_event(self, event: Event) -> None:
        if isinstance(event, Clear):
            self._chunks = []
            self._waiting = False
            self._reset_response()
            self._render_terminal()
        elif isinstance(event, Line):
            self._reset_response()
            terminal = self.query_one("#terminal", RichLog)
            width = terminal.size.width or SAY_WRAP_WIDTH
            lines = wrap_terminal_line(event.text, width) if event.wrap else [event.text]
            self._append("\n".join(lines) + "\n", LINE_STYLE.get(event.color, "white"))
            self._render_terminal()
        elif isinstance(event, Say):
            self._waiting = False
            self._say_style = "dim" if event.voice == "echo" else PALETTE_STYLE.get(self._palette, "white")
            await self._write_say_text(event.text, event.reveal)
            if event.line_end:
                await self._flush_say_word(event.reveal)
                self._end_response_line()
                if self._response_started:
                    self._append("\n", self._say_style)  # Blank separation between responses.
                self._reset_response()
                self._render_terminal()
        elif isinstance(event, Prompt):
            self._reset_response()
            self._prompt_label = (event.label or "YOU").upper()
            entry = self.query_one(Input)
            entry.placeholder = f"{self._prompt_label}> "
            entry.focus()
        elif isinstance(event, Palette):
            self._palette = event.name.lower()
            self.screen.remove_class("amber", "cga1", "cga2", "ega", "vga")
            self.screen.add_class(self._palette)
        elif isinstance(event, (Bell, Beep, KeyclickMode)):
            if not isinstance(event, KeyclickMode) or event.on:
                self.bell()
        if event.delay_ms:
            await asyncio.sleep(event.delay_ms / 1000)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value
        if not text:
            return
        event.input.value = ""
        self._append(f" {self._prompt_label}> {text}\n", "dim")
        self._waiting = True
        self._render_terminal()
        self.inputs.push(text)

    def on_unmount(self) -> None:
        self.inputs.close()


def run_tui(args: EngineArgs) -> None:
    SbaitsoApp(args).run()
