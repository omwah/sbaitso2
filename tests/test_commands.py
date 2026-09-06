from sbaitso.events import Line, Palette, Quit, Say

from conftest import events_of, says_of


def test_user_controlled_file_and_shell_commands_are_not_recognized(engine):
    assert not engine.commands.recognizes(".READ /etc/passwd")
    assert not engine.commands.recognizes("DOSSHELL echo UNSAFE")


async def test_help_pager(engine):
    ev1 = await events_of(engine, "HELP")
    lines1 = [e.text for e in ev1 if isinstance(e, Line)]
    assert any("PAGE 1 OF 3" in t for t in lines1)

    ev2 = await events_of(engine, "M")
    lines2 = [e.text for e in ev2 if isinstance(e, Line)]
    assert any("PAGE 2 OF 3" in t for t in lines2)

    ev3 = await events_of(engine, "M")
    lines3 = [e.text for e in ev3 if isinstance(e, Line)]
    assert any("PAGE 3 OF 3" in t for t in lines3)


async def test_empty_retro_turn_uses_documented_nothing_response(engine):
    from sbaitso.retro import NOTHING_RESPONSES

    ev = await events_of(engine, "")
    assert " ".join(says_of(ev)) in NOTHING_RESPONSES


async def test_m_only_after_help(engine):
    # "M" without HELP active is conversation, not a command
    ev = await events_of(engine, "M")
    assert all(not isinstance(e, Quit) for e in ev)
    says = says_of(ev)
    assert len(says) > 0  # retro brain answered


async def test_repeat(engine):
    ev = await events_of(engine, "hello")
    first = "\n".join(says_of(ev))
    ev2 = await events_of(engine, "R")
    assert "\n".join(says_of(ev2)) == first


async def test_say_command(engine):
    ev = await events_of(engine, "say testing one two")
    assert says_of(ev) == ["testing one two"]


async def test_math_command(engine):
    ev = await events_of(engine, "math 6*7")
    assert "42" in says_of(ev)[0]


async def test_quit_command(engine):
    ev = await events_of(engine, "EXIT")
    assert engine.quitting is True


async def test_color_command(engine):
    ev = await events_of(engine, "COLOR EGA")
    assert any(isinstance(e, Palette) and e.name == "ega" for e in ev)
    assert engine.settings.palette == "ega"


async def test_parity_say_parity(engine):
    ev = await events_of(engine, "say parity")
    text = " ".join(says_of(ev))
    assert "PARITY ERROR" in text


async def test_parity_long_input(engine):
    ev = await events_of(engine, "A" * 600)
    text = " ".join(says_of(ev))
    assert "PARITY ERROR" in text
    assert "JUST KIDDING" in text


async def test_dot_volume(engine):
    ev = await events_of(engine, ".VOLUME 3")
    assert "VOLUME SET TO 3" in " ".join(says_of(ev))
    ev = await events_of(engine, ".VOLUME 99")
    assert "0 TO 9" in " ".join(says_of(ev))


async def test_voice_command(engine):
    from sbaitso.events import VoiceEnabled

    ev = await events_of(engine, "VOICE")
    assert "MY VOICE IS ON" in " ".join(says_of(ev))

    ev = await events_of(engine, "VOICE OFF")
    assert engine.settings.voice_on is False
    assert any(isinstance(e, VoiceEnabled) and e.on is False for e in ev)
    assert "I SHALL BE SILENT." in " ".join(says_of(ev))

    ev = await events_of(engine, "VOICE ON")
    assert engine.settings.voice_on is True
    assert "I WILL SPEAK." in " ".join(says_of(ev))

    ev = await events_of(engine, "VOICE MAYBE")
    assert "ON OR OFF" in " ".join(says_of(ev))


async def test_brain_command(engine):
    ev = await events_of(engine, "BRAIN")
    text = " ".join(says_of(ev))
    assert "ACTIVE BRAIN" in text
    assert "RETRO" in text


async def test_brain_retro_switch_adds_retro_to_an_explicit_brain_session():
    from sbaitso.brains import RetroBrain
    from sbaitso.engine import Engine, EngineArgs

    ollama_only = Engine.from_args(EngineArgs(brain="ollama"))
    ev = await events_of(ollama_only, "BRAIN RETRO")

    assert isinstance(ollama_only.brain, RetroBrain)
    assert any(isinstance(brain, RetroBrain) for brain in ollama_only.brains)
    assert "RETRO MODE ENGAGED" in " ".join(says_of(ev))


async def test_patient_llm_turn_limit_comes_from_engine_configuration():
    from sbaitso.engine import Engine, EngineArgs

    assert EngineArgs().patient_llm_max_turns == 256
    configured = Engine.from_args(EngineArgs(brain="retro", patient_llm_max_turns=2))
    ev = await events_of(configured, "PATIENT LLM 3")
    assert "1 TO 2" in " ".join(says_of(ev))


async def test_patient_llm_runs_an_autonomous_retro_doctor_session():
    from sbaitso.brains import Brain, BrainContext, RetroBrain
    from sbaitso.engine import Engine, EngineArgs

    class PatientBrain(Brain):
        name = "TEST PATIENT LLM"
        down = False

        async def healthy(self):
            return True

        async def stream(self, messages, ctx):
            self.messages = messages
            yield "I AM WORRIED ABOUT MY WORK."

    patient = PatientBrain()
    retro = RetroBrain(Engine._shared_retro())
    autonomous = Engine([patient, retro], EngineArgs(brain="retro"))
    autonomous.history.append({"role": "user", "content": "I AM STRESSED ABOUT MY JOB."})

    ev = await events_of(autonomous, "PATIENT LLM 2")
    text = says_of(ev)
    assert sum(line.startswith("PATIENT>") for line in text) == 2
    assert sum(line.startswith("DR. SBAITSO>") for line in text) == 2
    assert sum(isinstance(event, Line) and event.text == "" for event in ev) == 4
    assert any("DEMONSTRATION COMPLETE" in line for line in text)
    assert "HUMAN: I AM STRESSED ABOUT MY JOB." in patient.messages[1]["content"]
    assert isinstance(autonomous.brain, RetroBrain)


async def test_dir_command(engine):
    engine.memory.note_user("i am stressed about work")
    ev = await events_of(engine, "DIR")
    lines = [e.text for e in ev if isinstance(e, Line)]
    assert any("RAM ONLY" in t for t in lines)


async def test_mood_command(engine):
    engine.memory.note_user("i feel great")
    ev = await events_of(engine, "MOOD")
    lines = [e.text for e in ev if isinstance(e, Line)]
    assert any("GREAT" in t for t in lines)
