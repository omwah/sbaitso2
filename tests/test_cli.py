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
    assert output == " HELLO.\n YOU> "
