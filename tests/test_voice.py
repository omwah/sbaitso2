from sbaitso.events import VoiceEnabled, VoiceParams
from sbaitso.voice import VoiceState, espeak_args


def test_espeak_args_defaults():
    state = VoiceState()  # tone=1, volume=5, pitch=5, speed=5
    args = espeak_args(state)
    assert args[0] == "-v" and args[1] == "en-us+f2"
    # pitch 5 -> 5+50=55, +5 treble = 60
    assert args[args.index("-p") + 1] == "60"
    # speed 5 -> 100+150=250
    assert args[args.index("-s") + 1] == "250"
    # volume 5 -> ~111
    assert args[args.index("-a") + 1] == "111"


def test_espeak_args_bass_and_echo():
    state = VoiceState()
    state.tone = 0  # bass
    args = espeak_args(state)
    assert args[args.index("-p") + 1] == "35"  # 55-20
    state.tone = 1
    args = espeak_args(state, echo=True)
    assert args[1] == "en-us+f3"
    assert args[args.index("-p") + 1] == "70"  # 55+15


def test_espeak_args_scales():
    state = VoiceState(volume=0, pitch=0, speed=0)
    args = espeak_args(state)
    assert args[args.index("-a") + 1] == "0"
    # pitch 0 with default treble tone: 5 + 0 + 5
    assert args[args.index("-p") + 1] == "10"
    assert args[args.index("-s") + 1] == "100"
    state = VoiceState(volume=9, pitch=9, speed=9)
    args = espeak_args(state)
    assert args[args.index("-a") + 1] == "200"
    # pitch 9 + treble clamps at espeak's 99
    assert args[args.index("-p") + 1] == "99"
    assert args[args.index("-s") + 1] == "370"
    # flat tone: pure pitch scale
    state = VoiceState(volume=9, pitch=9, speed=9, tone=1)
    state.tone = 1
    # sanity: bass variant lowers it (95-20)
    state.tone = 0
    args = espeak_args(state)
    assert args[args.index("-p") + 1] == "75"


def test_voice_state_updates():
    state = VoiceState()
    state.update(VoiceParams(pitch=2, speed=1))
    assert state.pitch == 2 and state.speed == 1
    assert state.volume == 5 and state.tone == 1  # untouched
    state.update(VoiceParams(tone=0, volume=9))
    assert state.tone == 0 and state.volume == 9
    state.update(VoiceEnabled(on=False))
    assert state.on is False
