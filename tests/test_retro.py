from sbaitso.retro import NOTHING_RESPONSES, RetroEngine, _safe_eval


def test_empty_input_uses_documented_nothing_responses():
    assert RetroEngine().respond("") in NOTHING_RESPONSES


def test_math_basic():
    r = RetroEngine()
    out = r.respond("what is 2+2", "MIKE")
    assert "4" in out
    assert "MIKE" in out


def test_math_precedence():
    r = RetroEngine()
    out = r.respond("what is 2+2*3", "MIKE")
    assert "8" in out


def test_my_phrase_uses_a_single_response_tuple():
    assert RetroEngine().respond("my work", "MIKE") == "TELL ME MORE ABOUT YOUR WORK, MIKE."


def test_reflection():
    r = RetroEngine()
    out = r.respond("i feel sad today", "MIKE")
    assert "SAD TODAY" in out  # "i feel sad today" -> why do you feel sad today
    assert "WHY DO YOU FEEL" in out


def test_greeting_uses_name():
    r = RetroEngine()
    out = r.respond("hello", "MIKE")
    assert out in {
        "HELLO MIKE, I AM DOCTOR SBAITSO, WHAT IS YOUR PROBLEM?",
        "HOW DO YOU DO, PLEASE ASK ME ANYTHING.",
        "HOW DO YOU DO MIKE, WHAT IS YOUR PROBLEM?",
        "NICE TO MEET YOU MIKE, TELL ME YOUR PROBLEMS.",
    }


def test_documented_retro_triggers():
    r = RetroEngine()

    assert r.respond("what is your name?", "MIKE") == (
        "MY NAME IS DOCTOR SBAITSO, NICE TO MEET YOU MIKE."
    )
    assert r.respond("echo echo", "MIKE") in {
        "AGAIN?", "ALWAYS REPEATING.", "DONT SAY THE SAME OLD THING.",
        "HAVE YOU RUN OUT OF WORDS TO SAY?", "I DONT LIKE PEOPLE REPEATING.",
        "MUST YOU ALWAYS SAY THE SAME THING?", "NO NONSENSE, DEAR.",
        "PLEASE DONT REPEAT.", "PLEASE SAY SOMETHING ELSE.",
        "SAY SOMETHING ELSE.", "THIS IS STALE STUFF.", "TRY SOMETHING ELSE.",
    }
    assert r.respond("computer", "MIKE") in {
        "ARE YOU TALKING ABOUT ME OR YOUR COMPUTER?",
        "DO YOU THINK COMPUTERS CAN HELP PEOPLE?",
        "TALKING OF TALKING COMPUTERS, DO YOU KNOW I AM ONE OF THE BEST AROUND?",
    }


def test_think_uses_the_non_canon_compatibility_pool():
    out = RetroEngine().respond("i think a lot", "MIKE")
    assert out in {
        "THINKING CAN BE DANGEROUS. CONTINUE.",
        "DO YOU THINK BEFORE YOU TYPE, OR AFTER?",
        "MY THINKING CIRCUITS ARE BUSY. WHAT ABOUT YOURS?",
        "THINK OF SOMETHING PLEASANT, MIKE.",
        "I THINK THEREFORE I COMPUTE.",
        "TO THINK IS HUMAN. TO COMPUTE IS SBAITSO.",
        "WHAT THOUGHT IS TROUBLING YOU, MIKE?",
        "THINKING TOO MUCH CAN CAUSE A PARITY ERROR.",
        "DO YOU WANT ME TO THINK FOR YOU?",
        "THATS A THOUGHT. KEEP GOING.",
    }


def test_no_immediate_repeat():
    r = RetroEngine()
    a = r.respond("the weather is something we discuss", None)
    b = r.respond("there are many topics in this world", None)
    assert a != b


def test_safe_eval_rejects_garbage():
    assert _safe_eval("import os") is None
    assert _safe_eval("2+2") == 4.0
    assert _safe_eval("hello world") is None
