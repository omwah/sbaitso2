from sbaitso.cli import build_parser
from sbaitso.llm import RemoteClient
from sbaitso.tui import SbaitsoApp
from sbaitso.engine import EngineArgs


def test_remote_provider_autodetection(monkeypatch):
    monkeypatch.delenv("SBAITSO_REMOTE_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    remote = RemoteClient()
    assert remote.provider == "GROQ_API_KEY"
    assert remote.base_url == "https://api.groq.com/openai/v1"
    assert remote.api_key == "test-key"


def test_explicit_remote_settings_override_autodetection(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "detected-key")
    remote = RemoteClient(api_key="explicit-key", base_url="https://example.test/v1", model="custom")
    assert remote.provider == "custom"
    assert remote.api_key == "explicit-key"
    assert remote.base_url == "https://example.test/v1"
    assert remote.model == "custom"


def test_tui_subcommand_is_available():
    assert build_parser().parse_args(["tui", "--brain", "retro"]).cmd == "tui"


async def test_textual_tui_mounts():
    app = SbaitsoApp(EngineArgs(brain="retro", fast=True))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#terminal") is not None
