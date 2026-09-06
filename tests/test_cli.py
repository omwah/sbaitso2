import re

import pytest

import sbaitso.cli as cli
from sbaitso.cli import Renderer, build_parser, engine_args_from_namespace
from sbaitso.events import Prompt, Say


def test_color_option_configures_the_engine_palette():
    args = build_parser().parse_args(["run", "--color", "amber"])
    assert engine_args_from_namespace(args).palette == "amber"


@pytest.mark.parametrize(
    ("name", "background"),
    [("cga1", "#0000aa"), ("cga2", "#000000"), ("ega", "#000055"),
     ("vga", "#0a0a0a"), ("amber", "#160400")],
)
def test_native_color_themes_emit_full_terminal_palettes(monkeypatch, name, background):
    class TtyOutput:
        def __init__(self):
            self.text = ""

        def isatty(self):
            return True

        def write(self, text):
            self.text += text

        def flush(self):
            pass

    output = TtyOutput()
    monkeypatch.setattr(cli.sys, "stdout", output)
    cli.apply_native_palette(name)
    assert f"\x1b]11;{background}\x07" in output.text
    assert "\x1b]4;15;" in output.text


@pytest.mark.asyncio
async def test_cli_responses_and_prompts_match_boot_gutter(capsys):
    renderer = Renderer(fast=True, voice=False)

    await renderer.render(Say("HELLO."))
    await renderer.render(Prompt("YOU"))

    output = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert output == " HELLO.\n\n YOU> "


@pytest.mark.asyncio
async def test_cli_intake_prompts_match_main_prompt_spacing(capsys):
    renderer = Renderer(fast=True, voice=False)

    await renderer.render(Say("HELLO."))
    await renderer.render(Prompt("AGE"))

    output = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert output == " HELLO.\n\n AGE> "


@pytest.mark.asyncio
async def test_cli_does_not_emit_lines_for_empty_or_terminated_say_text(capsys):
    renderer = Renderer(fast=True, voice=False)

    await renderer.render(Say(""))
    await renderer.render(Say("HELLO.\n"))

    output = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert output == " HELLO.\n"
