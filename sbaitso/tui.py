"""Textual fullscreen frontend for the shared Sbaitso engine."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, RichLog, Static

from .engine import Engine, EngineArgs, Inputs
from .events import Bell, Beep, Clear, Event, KeyclickMode, Line, Palette, Prompt, Quit, Say


class SbaitsoApp(App[None]):
    """A DOS-styled Textual adapter; all conversation remains in Engine."""

    CSS = """
    Screen { background: #0000aa; color: #ffffff; }
    #title { height: 1; background: #0000aa; color: #ffff55; text-style: bold; }
    #terminal { height: 1fr; background: #0000aa; color: #ffffff; border: solid #55ffff; }
    #entry { dock: bottom; background: #0000aa; color: #ffffff; border: solid #55ffff; }
    Screen.amber { background: #1a1000; color: #ffb000; }
    Screen.amber #title, Screen.amber #terminal, Screen.amber #entry { background: #1a1000; color: #ffb000; border: solid #ffb000; }
    Screen.cga1 { background: #000000; color: #55ffff; }
    Screen.cga2 { background: #000000; color: #ff55ff; }
    """

    def __init__(self, args: EngineArgs) -> None:
        super().__init__()
        self.engine = Engine.from_args(args)
        self.inputs = Inputs()
        self._runner: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(" DR. SBAITSO/2 — TEXTUAL TERMINAL ", id="title")
            yield RichLog(id="terminal", wrap=True, highlight=False, markup=False)
            yield Input(placeholder="YOU> ", id="entry")

    def on_mount(self) -> None:
        self._runner = asyncio.create_task(self._run_engine())
        self.query_one(Input).focus()

    async def _run_engine(self) -> None:
        async for event in self.engine.run(self.inputs):
            await self.render_event(event)
            if isinstance(event, Quit):
                self.exit()
                return

    async def render_event(self, event: Event) -> None:
        log = self.query_one(RichLog)
        if isinstance(event, Clear):
            log.clear()
        elif isinstance(event, (Line, Say)):
            log.write(event.text)
        elif isinstance(event, Prompt):
            entry = self.query_one(Input)
            entry.placeholder = f"{(event.label or 'YOU').upper()}> "
            entry.focus()
        elif isinstance(event, Palette):
            self.screen.remove_class("amber", "cga1", "cga2")
            if event.name.lower() in {"amber", "cga1", "cga2"}:
                self.screen.add_class(event.name.lower())
        elif isinstance(event, (Bell, Beep, KeyclickMode)):
            if not isinstance(event, KeyclickMode) or event.on:
                self.bell()
        if event.delay_ms:
            await asyncio.sleep(event.delay_ms / 1000)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value
        event.input.value = ""
        self.inputs.push(text)

    def on_unmount(self) -> None:
        self.inputs.close()


def run_tui(args: EngineArgs) -> None:
    SbaitsoApp(args).run()
