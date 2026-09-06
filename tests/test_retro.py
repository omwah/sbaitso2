from sbaitso.retro import RetroEngine, _safe_eval


def test_math_basic():
    r = RetroEngine()
    out = r.respond("what is 2+2", "MIKE")
    assert "4" in out
    assert "MIKE" in out


def test_math_precedence():
    r = RetroEngine()
    out = r.respond("what is 2+2*3", "MIKE")
    assert "8" in out


def test_reflection():
    r = RetroEngine()
    out = r.respond("i feel sad today", "MIKE")
    assert "SAD TODAY" in out  # "i feel sad today" -> why do you feel sad today
    assert "WHY DO YOU FEEL" in out


def test_greeting_uses_name():
    r = RetroEngine()
    out = r.respond("hello", "MIKE")
    assert out.startswith("HELLO, MIKE")


def test_no_immediate_repeat():
    r = RetroEngine()
    a = r.respond("the weather is something we discuss", None)
    b = r.respond("there are many topics in this world", None)
    assert a != b


def test_safe_eval_rejects_garbage():
    assert _safe_eval("import os") is None
    assert _safe_eval("2+2") == 4.0
    assert _safe_eval("hello world") is None
