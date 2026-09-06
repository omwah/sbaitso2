"""Native terminal frontend. Runs the core in-process; no server.

Supports a real tty (raw char mode, manual echo) and piped stdin.
Voice (espeak-ng) arrives in Phase 2; for now: BEL beeps + typewriter.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import os
import sys
from contextlib import contextmanager

try:  # POSIX only; Windows falls back to line input
    import termios
    import tty

    HAVE_TERMIOS = True
except ImportError:  # pragma: no cover - windows
    HAVE_TERMIOS = False

from .engine import Engine, EngineArgs, Inputs
from .events import (
    Bell, Beep, Clear, EchoMode, Event, Line, Palette, Prompt, Quit, Say,
    VoiceParams,
)

ANSI = {
    "white": "\x1b[97m",
    "cyan": "\x1b[96m",
    "yellow": "\x1b[93m",
    "green": "\x1b[92m",
    "red": "\x1b[91m",
    "dim": "\x1b[90m",
}
RESET = "\x1b[0m"

PALETTE_FG = {
    "cga1": ANSI["cyan"],
    "cga2": ANSI["green"],
    "ega": ANSI["white"],
    "vga": "\x1b[37m",
    "amber": "\x1b[33m",
}


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

    def __init__(self, loop: asyncio.AbstractEventLoop, inputs: Inputs) -> None:
        self.loop = loop
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
    def __init__(self, fast: bool) -> None:
        self.fast = fast
        self.say_color = PALETTE_FG["cga1"]

    async def render(self, ev: Event) -> None:
        if isinstance(ev, Line):
            if ev.delay_ms:
                await asyncio.sleep(ev.delay_ms / 1000)
            print(f"{ANSI.get(ev.color, '')}{ev.text}{RESET}")
        elif isinstance(ev, Say):
            if ev.delay_ms:
                await asyncio.sleep(ev.delay_ms / 1000)
            color = ANSI["dim"] if ev.voice == "echo" else self.say_color
            if ev.reveal and not self.fast:
                for ch in ev.text:
                    sys.stdout.write(f"{color}{ch}{RESET}")
                    sys.stdout.flush()
                    await asyncio.sleep(0.012)
                sys.stdout.write("\n")
            else:
                print(ev.text if not ev.reveal else f"{color}{ev.text}{RESET}")
            sys.stdout.flush()
        elif isinstance(ev, (Beep, Bell)):
            sys.stdout.write("\a")
            sys.stdout.flush()
        elif isinstance(ev, Palette):
            self.say_color = PALETTE_FG.get(ev.name, self.say_color)
            print(f"{ANSI['yellow']}PALETTE: {ev.name.upper()}{RESET}")
        elif isinstance(ev, Clear):
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.flush()
        elif isinstance(ev, Prompt):
            label = (ev.label or "YOU").upper()
            print(f"{ANSI['dim']}{label}> {RESET}", end="", flush=True)
        elif isinstance(ev, (VoiceParams, EchoMode)):
            pass  # Phase 2: espeak-ng honors these
        elif isinstance(ev, Quit):
            pass


async def _run(args: argparse.Namespace) -> None:
    engine_args = EngineArgs(
        brain=args.brain,
        ollama_url=args.ollama_url,
        model=args.model,
        remote_url=args.remote_url,
        remote_model=args.remote_model,
        remote_key=args.remote_key,
        sass=args.sass,
        palette=args.palette,
        allow_shell=args.doshell,
        fast=args.fast,
    )
    engine = Engine.from_args(engine_args)
    inputs = Inputs()
    renderer = Renderer(fast=args.fast)

    with raw_stdin() as is_tty:
        loop = asyncio.get_running_loop()
        reader = KeyReader(loop, inputs)
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
            print(RESET, end="")


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
        sp.add_argument("--palette", choices=list(PALETTE_FG), default="cga1")
        sp.add_argument("--doshell", action="store_true", help="enable DOSSHELL command")
        sp.add_argument("--fast", action="store_true", help="skip typewriter pacing")

    serve = sub.add_parser("serve", help="run the web frontend")
    common(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    native = sub.add_parser("run", help="run the native terminal frontend (default)")
    common(native)
    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    # default subcommand: run
    if not argv or (argv[0] != "run" and argv[0] != "serve"):
        argv = ["run"] + argv
    args = build_parser().parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        from .main import app

        uvicorn.run(app, host=args.host, port=args.port)
    else:
        asyncio.run(_run(args))


if __name__ == "__main__":
    main()
