"""Native terminal frontend. Runs the core in-process; no server.

Supports a real tty (raw char mode, manual echo) and piped stdin.
Voice (espeak-ng) arrives in Phase 2; for now: BEL beeps + typewriter.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import os
import shutil
import sys
import textwrap
from contextlib import contextmanager

try:  # POSIX only; Windows falls back to line input
    import termios
    import tty

    HAVE_TERMIOS = True
except ImportError:  # pragma: no cover - windows
    HAVE_TERMIOS = False

from .engine import Engine, EngineArgs, Inputs
from .events import (
    Bell, Beep, Clear, Event, KeyclickMode, Line, Palette, Prompt, Quit, Say,
    VoiceEnabled, VoiceParams,
)
from .voice import EspeakVoice, VoiceState, available

ANSI = {
    "white": "\x1b[97m",
    "cyan": "\x1b[96m",
    "yellow": "\x1b[93m",
    "green": "\x1b[92m",
    "red": "\x1b[91m",
    "dim": "\x1b[90m",
}
RESET = "\x1b[0m"
SAY_WRAP_WIDTH = 72
RESPONSE_INDENT = " "


def wrap_terminal_line(text: str, width: int) -> list[str]:
    """Wrap a boot/listing line at word boundaries without splitting words."""
    if not text:
        return [""]
    return textwrap.wrap(
        text,
        width=max(1, width),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]

PALETTE_FG = {
    "cga1": ANSI["cyan"],
    "cga2": ANSI["green"],
    "ega": ANSI["white"],
    "vga": "\x1b[37m",
    "amber": "\x1b[33m",
}

# OSC palette control is supported by xterm-compatible terminals. Unsupported
# terminals ignore it and keep the existing ANSI foreground-only fallback.
_STANDARD_ANSI = (
    "#000000", "#aa0000", "#00aa00", "#aa5500",
    "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa",
    "#555555", "#ff5555", "#55ff55", "#ffff55",
    "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
)
PALETTE_TERMINALS = {
    "cga1": ("#0000aa", "#55ffff", "#55ffff", _STANDARD_ANSI),
    "cga2": ("#000000", "#55ff55", "#55ff55", _STANDARD_ANSI),
    "ega": ("#000055", "#ffffff", "#ffffff", _STANDARD_ANSI),
    "vga": ("#0a0a0a", "#c8c8c8", "#c8c8c8", _STANDARD_ANSI),
    "amber": (
        "#160400", "#ffb347", "#ffd36b",
        (
            "#260700", "#ff7a24", "#ff9a3d", "#ffc35a",
            "#b95a1b", "#e07025", "#ffb347", "#ffd18a",
            "#7a3515", "#ff8a32", "#ffad4d", "#ffd36b",
            "#d76a22", "#f08a35", "#ffd18a", "#ffe0a3",
        ),
    ),
}


def apply_native_palette(name: str) -> None:
    """Apply a terminal theme where OSC palette controls are supported."""
    if not sys.stdout.isatty():
        return
    background, foreground, cursor, ansi_colors = PALETTE_TERMINALS[name]
    ansi = "".join(
        f"\x1b]4;{index};{color}\x07" for index, color in enumerate(ansi_colors)
    )
    sys.stdout.write(
        ansi + f"\x1b]10;{foreground}\x07\x1b]11;{background}\x07\x1b]12;{cursor}\x07"
    )
    sys.stdout.flush()


def reset_native_palette() -> None:
    """Restore the user's terminal colors after the native client exits."""
    if sys.stdout.isatty():
        sys.stdout.write("\x1b]104\x07\x1b]110\x07\x1b]111\x07\x1b]112\x07")
        sys.stdout.flush()


@contextmanager
def raw_stdin():
    if not HAVE_TERMIOS or not sys.stdin.isatty():
        yield False
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


class KeyReader:
    """Read stdin char-by-char on the event loop; push lines to Inputs."""

    def __init__(self, loop: asyncio.AbstractEventLoop, inputs: Inputs, click_fn=None) -> None:
        self.loop = loop
        self.click_fn = click_fn
        self.inputs = inputs
        self.buf = ""
        self._fd = sys.stdin.fileno()
        self._active = False

    def start(self) -> None:
        if not sys.stdin.isatty():
            return
        self._active = True
        self.loop.add_reader(self._fd, self._on_readable)

    def stop(self) -> None:
        if self._active:
            self.loop.remove_reader(self._fd)
            self._active = False

    def _on_readable(self) -> None:
        data = os.read(self._fd, 64).decode(errors="ignore")
        for ch in data:
            if self.click_fn and ch in ("\r", "\n", "\x7f", "\x08") or (self.click_fn and ch >= " "):
                self.click_fn()
            if ch in ("\r", "\n"): 
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                self.inputs.push(self.buf)
                self.buf = ""
            elif ch in ("\x7f", "\x08"):
                if self.buf:
                    self.buf = self.buf[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch in ("\x03", "\x04"):  # Ctrl-C / Ctrl-D
                sys.stdout.write("^C\r\n" if ch == "\x03" else "^D\r\n")
                sys.stdout.flush()
                self.inputs.close()
                self.stop()
            elif ch >= " ":
                self.buf += ch
                sys.stdout.write(ch)
                sys.stdout.flush()


class Renderer:
    def __init__(self, fast: bool, voice: bool = True) -> None:
        self.fast = fast
        self.say_color = PALETTE_FG["vga"]
        self.voice_on = voice and available()
        self.voice_state = VoiceState()
        self.espeak = EspeakVoice() if self.voice_on else None
        self.say_column = 0
        self.say_word = ""
        self.keyclick_on = True

    def click(self) -> None:
        if self.keyclick_on:
            sys.stdout.write("\a")
            sys.stdout.flush()

    def _ensure_response_indent(self, color: str) -> None:
        if self.say_column == 0:
            sys.stdout.write(f"{color}{RESPONSE_INDENT}{RESET}")
            self.say_column = len(RESPONSE_INDENT)

    async def _write_char(self, ch: str, color: str, reveal: bool) -> None:
        sys.stdout.write(f"{color}{ch}{RESET}")
        self.say_column += 1
        if reveal and not self.fast:
            sys.stdout.flush()
            await asyncio.sleep(0.012)

    async def _flush_say_word(self, color: str, reveal: bool) -> None:
        """Emit a complete pending word, wrapping before rather than within it."""
        if not self.say_word:
            return
        if self.say_column and self.say_column + len(self.say_word) > SAY_WRAP_WIDTH:
            sys.stdout.write("\n")
            self.say_column = 0
        self._ensure_response_indent(color)
        for ch in self.say_word:
            if self.say_column >= SAY_WRAP_WIDTH:
                sys.stdout.write("\n")
                self.say_column = 0
                self._ensure_response_indent(color)
            await self._write_char(ch, color, reveal)
        self.say_word = ""

    async def _write_say_text(self, text: str, color: str, reveal: bool) -> None:
        """Word-wrap streamed text at a stable, DOS-like response width."""
        for ch in text:
            if ch == "\n":
                await self._flush_say_word(color, reveal)
                if self.say_column:
                    sys.stdout.write("\n")
                    self.say_column = 0
            elif ch.isspace():
                await self._flush_say_word(color, reveal)
                if self.say_column < SAY_WRAP_WIDTH:
                    await self._write_char(ch, color, reveal)
            else:
                self.say_word += ch

    async def render(self, ev: Event) -> None:
        if isinstance(ev, Line):
            if ev.delay_ms:
                await asyncio.sleep(ev.delay_ms / 1000)
            width = shutil.get_terminal_size(fallback=(SAY_WRAP_WIDTH, 24)).columns
            lines = wrap_terminal_line(ev.text, width) if ev.wrap else [ev.text]
            print(f"{ANSI.get(ev.color, '')}{chr(10).join(lines)}{RESET}")
            self.say_column = 0
            self.say_word = ""
        elif isinstance(ev, Say):
            if ev.delay_ms:
                await asyncio.sleep(ev.delay_ms / 1000)
            color = ANSI["dim"] if ev.voice == "echo" else self.say_color
            speech = None
            spoken_text = ev.speech_text or ev.text
            if self.espeak and self.voice_state.on and not ev.partial:
                speech = await self.espeak.speak(
                    spoken_text, self.voice_state, echo=ev.voice == "echo"
                )
            await self._write_say_text(ev.text, color, ev.reveal)
            if ev.line_end:
                await self._flush_say_word(color, ev.reveal)
                if self.say_column:
                    sys.stdout.write("\n")
                    self.say_column = 0
            sys.stdout.flush()
            if speech:
                await speech
        elif isinstance(ev, (Beep, Bell)):
            sys.stdout.write("\a")
            sys.stdout.flush()
        elif isinstance(ev, KeyclickMode):
            self.keyclick_on = ev.on
        elif isinstance(ev, Palette):
            self.say_color = PALETTE_FG.get(ev.name, self.say_color)
            apply_native_palette(ev.name)
            if ev.announce:
                print(f"{ANSI['yellow']}PALETTE: {ev.name.upper()}{RESET}")
            self.say_column = 0
            self.say_word = ""
        elif isinstance(ev, Clear):
            sys.stdout.write("\x1b[2J\x1b[H")
            self.say_column = 0
            self.say_word = ""
            sys.stdout.flush()
        elif isinstance(ev, Prompt):
            label = (ev.label or "YOU").upper()
            print(f"\n{ANSI['dim']}{RESPONSE_INDENT}{label}> {RESET}", end="", flush=True)
            self.say_column = 0
            self.say_word = ""
        elif isinstance(ev, (VoiceParams, VoiceEnabled)):
            self.voice_state.update(ev)
        elif isinstance(ev, Quit):
            if self.espeak:
                await self.espeak.drain()


def engine_args_from_namespace(args: argparse.Namespace) -> EngineArgs:
    return EngineArgs(
        brain=args.brain,
        ollama_url=args.ollama_url,
        model=args.model,
        remote_url=args.remote_url,
        remote_model=args.remote_model,
        remote_key=args.remote_key,
        sass=args.sass,
        palette=args.color,
        fast=args.fast,
        debug_llm=getattr(args, "debug_llm", False),
    )


async def _run(args: argparse.Namespace) -> int:
    engine = Engine.from_args(engine_args_from_namespace(args))
    inputs = Inputs()
    renderer = Renderer(fast=args.fast, voice=not args.novoice)

    with raw_stdin() as is_tty:
        loop = asyncio.get_running_loop()
        reader = KeyReader(loop, inputs, renderer.click)
        reader.start()
        if not is_tty:
            _start_line_input(loop, inputs)
        try:
            async for ev in engine.run(inputs):
                await renderer.render(ev)
                if isinstance(ev, Quit):
                    break
        except KeyboardInterrupt:
            print("\r\n^C INTERRUPT RECEIVED.\r")
            for ev in engine.prescription_events():
                await renderer.render(ev)
        finally:
            reader.stop()
            reset_native_palette()
            print(RESET, end="")
    return 1 if engine.startup_error else 0


def _start_line_input(loop: asyncio.AbstractEventLoop, inputs: Inputs) -> None:
    """Line-mode input for non-tty stdin (pipes) and platforms without
    termios (Windows). Runs in a worker thread so the event loop stays live.
    EOF closes the session."""

    _background: set = set()

    async def wrapper() -> None:
        await loop.run_in_executor(None, _pump_sync, inputs)

    def _pump_sync(inputs: Inputs) -> None:
        for line in sys.stdin:
            inputs.push(line.rstrip("\n"))
        inputs.close()

    task = loop.create_task(wrapper())
    _background.add(task)
    task.add_done_callback(_background.discard)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sbaitso",
        description="DR. SBAITSO/2 - a modern chatbot with a 1991 DOS soul",
    )
    sub = p.add_subparsers(dest="cmd")

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--brain", choices=["auto", "ollama", "remote", "retro"], default="auto")
        sp.add_argument("--ollama-url", default=None)
        sp.add_argument("--model", default=None)
        sp.add_argument("--remote-url", default=None)
        sp.add_argument("--remote-model", default=None)
        sp.add_argument("--remote-key", default=None)
        sp.add_argument("--sass", choices=["LOW", "NORMAL", "HIGH"], default="NORMAL")
        sp.add_argument("--color", choices=list(PALETTE_FG), default="vga")
        sp.add_argument("--fast", action="store_true", help="skip typewriter pacing")
        sp.add_argument("--novoice", action="store_true", help="disable espeak-ng voice (if installed)")

    serve = sub.add_parser("serve", help="run the web frontend")
    common(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    native = sub.add_parser("run", help="run the native terminal frontend (default)")
    common(native)
    native.add_argument(
        "--debug-llm",
        action="store_true",
        help="print outbound Ollama/remote JSON messages (never headers or API keys)",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    # default subcommand: run
    if not argv or (argv[0] != "run" and argv[0] != "serve"):
        argv = ["run"] + argv
    args = build_parser().parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        from .main import app, configure

        configure(engine_args_from_namespace(args))
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
