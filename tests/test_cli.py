import re

import pytest

from sbaitso.cli import Renderer
from sbaitso.events import Prompt, Say


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
