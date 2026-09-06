from sbaitso.memory import SessionMemory


def test_fact_extraction():
    mem = SessionMemory()
    mem.note_user("my name is mike and i work as a teacher")
    keys = {f.key for f in mem.facts}
    assert "NAME" in keys
    assert "JOB" in keys


def test_age_extraction():
    mem = SessionMemory()
    mem.note_user("i am 42 years old")
    assert mem.age == 42
    assert any(f.key == "AGE" for f in mem.facts)


def test_mood_extraction():
    mem = SessionMemory()
    mem.note_user("i feel sad today")
    assert mem.moods[-1].label == "SAD"
    mem.note_user("but it got better")
    assert mem.moods[-1].score == 1


def test_topic_extraction():
    mem = SessionMemory()
    mem.note_user("my boss is driving me crazy at work")
    assert "boss" in mem.topics
    assert "work" in mem.topics


def test_journal_heuristic_via_engine(engine):
    engine.memory.note_user("i am so stressed about my job")
    engine._record("i am so stressed about my job", "I SEE.")
    assert len(engine.memory.journal) == 1
    assert "STRESSED" in engine.memory.journal[0].title


def test_mood_trend():
    mem = SessionMemory()
    mem.note_user("i feel sad")
    mem.note_user("still sad")
    mem.note_user("feeling better now")
    assert mem.mood_trend() == "LIFTING"
