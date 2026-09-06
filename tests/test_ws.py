"""End-to-end websocket test against the FastAPI app (retro fallback).

The env var points Ollama probing at a dead local port so boot falls
through to RETRO v1 instantly — no network, deterministic.
"""

import os

import pytest

os.environ.setdefault("SBAITSO_OLLAMA_URL", "http://127.0.0.1:9")  # dead port

from fastapi.testclient import TestClient  # noqa: E402

from sbaitso.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["storage"] == "NONE (AS PROMISED)"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "SBAITSO" in r.text


def test_full_session(client):
    with client.websocket_connect("/ws") as ws:
        # boot -> name prompt
        events = collect_until(ws, "prompt")
        assert any(e["type"] == "line" and "SBAITSO/2" in e["text"] for e in events)
        ws.send_json({"type": "input", "text": "MIKE"})

        # -> age prompt
        events = collect_until(ws, "prompt")
        assert any(e["type"] == "say" and "HELLO, MIKE" in e["text"] for e in events)
        ws.send_json({"type": "input", "text": "42"})

        # -> conversation prompt
        events = collect_until(ws, "prompt")
        assert any(e["type"] == "say" and "386" in e["text"] for e in events)
        ws.send_json({"type": "input", "text": "i feel stressed about work"})

        # retro brain responds (no ollama on dead port)
        events = collect_until(ws, "prompt")
        says = [e["text"] for e in events if e["type"] == "say"]
        assert any("MIKE" in s for s in says)

        ws.send_json({"type": "input", "text": "EXIT"})
        events = collect_until(ws, "quit")
        text = " ".join(
            e.get("text", "") for e in events if e["type"] in ("say", "line")
        )
        assert "PRESCRIPTION" in text
        assert "REMEMBER NOTHING" in text


def test_voice_events_over_websocket(client):
    with client.websocket_connect("/ws") as ws:
        collect_until(ws, "prompt")
        ws.send_json({"type": "input", "text": "MIKE"})
        collect_until(ws, "prompt")
        ws.send_json({"type": "input", "text": "42"})
        collect_until(ws, "prompt")

        ws.send_json({"type": "input", "text": "VOICE OFF"})
        events = collect_until(ws, "prompt")
        assert any(e["type"] == "voiceenabled" and e["on"] is False for e in events)

        ws.send_json({"type": "input", "text": ".PARAM 1595"})
        events = collect_until(ws, "prompt")
        assert any(
            e["type"] == "voiceparams"
            and (e["tone"], e["volume"], e["pitch"], e["speed"]) == (1, 5, 9, 5)
            for e in events
        )

        ws.send_json({"type": "input", "text": "EXIT"})
        collect_until(ws, "quit")


def collect_until(ws, event_type, limit=500):
    events = []
    for _ in range(limit):
        ev = ws.receive_json()
        events.append(ev)
        if ev["type"] == event_type:
            break
    return events
