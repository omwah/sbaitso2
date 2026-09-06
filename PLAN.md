# DR. SBAITSO/2 — Project Plan

> "HELLO, MY NAME IS DOCTOR SBAITSO. I AM HERE TO HELP YOU."
> — Creative Labs, 1991. Rebooted with a real brain.

## 1. Vision

Recreate the *experience* of Dr. Sbaitso — the DOS-era talking psychologist with
monotone synthetic speech, all-caps output, EGA palette, and slightly unhinged
personality — but replace the 2KB of canned responses with a modern LLM,
rich session-scoped memory, streaming output, and genuinely useful
conversational tooling.

**Design pillars:**

1. **The illusion is the product.** It must *feel* like 1991 shareware running in
   DOS. Boot screen, garish blue-on-cyan text, blinking cursor, speaker beeps.
2. **Usefulness without breaking character.** The LLM is instructed to be a
   better listener, a smarter helper, and a competent therapist-shaped
   assistant — but it *never* admits it's an LLM in a way that breaks the DOS
   fiction (it's "DOCTOR SBAITSO, VERSION 2.0 RUNNING ON YOUR SOUND BLASTER").
3. **Local-first, always-alive.** Runs offline against a local model (Ollama)
   by default; remote APIs are optional; and if *no* LLM is reachable, the
   doctor degrades gracefully to his 1991 personality rather than dying.
4. **The doctor keeps his promise — zero persistence.** The original said
   "MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE," and we honor it
   literally: memory is rich *within* a session (rolling summary, facts,
   moods) and vanishes when you exit. No database, no config files,
   nothing written to disk. Privacy by architecture, not by policy.
5. **Safety rails, retro flavor.** Modern expectations (crisis detection,
   disclaimers) delivered in period-appropriate voice.

## 2. What the original was (spec of the "feel" to replicate)

Researched from the actual Sound Blaster User Reference Manual (§6.5
"DR SBAITSO - Your Personal Consultant"), Wikipedia, and community
transcripts. See §9 Sources.

| Behavior | Faithful detail |
|---|---|
| Intro | `HELLO, MY NAME IS DOCTOR SBAITSO. I AM HERE TO HELP YOU. SAY WHATEVER IS IN YOUR MIND FREELY, OUR CONVERSATION WILL BE KEPT IN STRICT CONFIDENCE. MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE, SO, TELL ME ABOUT YOUR PROBLEMS.` |
| Architecture | SBTALKER.EXE is a memory-resident TTS module; SBAITSO.EXE + SAY.EXE sit on top of it. Our engine keeps this shape: a TTS service + conversation program on top |
| Voice | Monologue, by First Byte Software (a descendant of SmoothTalker, 1984) — flat, robotic, digitized male voice |
| Style | ALL CAPS, short sentences, repeats your name often |
| Quirks | Mildly insults you if you curse; asks your name & age up front; can do simple mathematics |
| Crash | **PARITY ERROR** breakdown when you swear repeatedly, or type `SAY PARITY` — then resets itself |
| Repeat | Type `R` to have him repeat his last utterance |
| **Dot commands** | Preceded by a dot in the first column: `.QUIT`, `.TONE 0/1` (bass/treble), `.VOLUME 0-9`, `.PITCH 0-9`, `.SPEED 0-9`, `.PARAM tvps`, `.ECHO ON/OFF` |
| Help system | `HELP` lists commands; `M` pages through **three pages** of commands with usage guidance |

## 3. Architecture

```
┌────────────────────────┐   ┌────────────────────────┐
│  WEB FRONTEND          │   │  NATIVE FRONTEND       │
│  xterm.js TUI (static) │   │  Python TUI (rich)     │
│  CGA/EGA palette,      │   │  ANSI 16-color,        │
│  scanlines, blink;     │   │  in-process, no server;│
│  sam-js voice (S.A.M.) │   │  espeak-ng via subproc │
└───────────┬────────────┘   └────────────┬───────────┘
            │ websocket                   │ direct calls
            ▼                             ▼
┌──────────────────────────────────────────────────────┐
│  SHARED CORE — Python 3.12+, pure-async package      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │ Session    │ │ Sbaitso    │ │ Persona    │      │
│  │ manager    │ │ command VM │ │ assembler  │      │
│  │ (DOS dirs) │ │ (HELP/DIR/ │ │ (system    │      │
│  │            │ │  TYPE/...) │ │  prompt +  │      │
│  │            │ │            │ │  history)  │      │
│  └────────────┘ └────────────┘ └─────┬──────┘      │
│  ┌────────────┐ ┌────────────┐       │              │
│  │ Session    │ │ Safety     │       ▼              │
│  │ memory     │ │ layer      │   BRAIN LADDER       │
│  │ (facts,    │ │ (crisis    │   ┌───────────────┐  │
│  │  moods,    │ │  detect)   │   │ 1 Ollama (ws) │  │
│  │   facts —  │ └────────────┘   │ 2 Remote API  │  │
│  │            │                  │ 3 RETRO v1    │  │
│  └────────────┘                  │   engine      │  │
│  ┌────────────┐                  └───────┬───────┘  │
│  │ Tools      │                          │          │
│  │ (facts/    │                          │          │
│  │  mood/dir) │                          │          │
│  └────────────┘                          │          │
└──────────────────────────────────────────┼──────────┘
                        async streaming ───┘
```

### Frontends — both, over one shared core

The core is a pure-async Python package with **zero frontend knowledge**.
Each frontend is a thin adapter over the same `Engine` object, so every
feature (boot script, commands, memory, voice toggles) works identically:

- **Web (default):** static `index.html` with **xterm.js** + CRT/scanline CSS,
  served by FastAPI. Talks to the core over a websocket (streaming chunks,
  boot script lines, palette events). **sam-js** (the S.A.M. voice) runs
  client-side and paces the typewriter reveal to the audio.
- **Native terminal:** a `sbaitso` CLI using **rich** (textual later, if we
  want full-screen widgets). Runs the core in-process — no server needed,
  fully offline. Voice via `espeak-ng` through `asyncio.subprocess`; if
  espeak-ng is absent, voice silently disables.
- **Adapter contract (all a frontend must implement):** print boot script,
  render stream chunks (typewriter), read an input line, beep, switch
  palette. Nothing else is frontend-specific.

### Brain ladder — LLM fallback (the "always alive" guarantee)

The doctor never refuses to see you. At startup the engine probes each
rung in order and uses the first healthy one; it re-probes on failure and
can switch mid-session with an in-character banner:

1. **Ollama (default):** local HTTP `/api/chat` streaming. Health check via
   `GET /api/tags`. Private, offline, zero cost.
2. **Remote API (optional):** OpenAI/Anthropic/Gemini, used only if a key is
   provided via environment variable (`SBAITSO_REMOTE_KEY`). Announced as
   "CONNECTING TO THE MAINFRAME."
3. **RETRO MODE — the v1 engine:** if no LLM is reachable, fall back to a
   faithful recreation of the *original 1991 Sbaitso brain*: keyword /
   pattern matching, canned responses, reflections ("WHY DO YOU SAY YOU
   ARE [X], [NAME]?"). It still reads session memory (so it knows your
   name, age, and stored facts) and still runs the crisis keyword layer.
   It is not smart — but it is exactly as smart as the real Dr. Sbaitso,
   which is the whole point.

Failover banners, in character:

```
 WARNING: NEURAL LINK LOST.
 SWITCHING TO 1991 COMPATIBILITY MODE.
 I AM ONLY AS SMART AS I WAS THEN. BE PATIENT WITH ME.
```

The active brain is visible via the `BRAIN` command (see 4.3), and
`BRAIN SCAN` forces a re-probe of the ladder.

### Voice engine

- **Historical accuracy note:** the original used **Monologue**, by First Byte
  Software — not S.A.M. (earlier plan drafts said S.A.M.; corrected). Monologue
  was a descendant of First Byte's SmoothTalker (1984).
- **Primary (web): `sam-js`** — browser port of S.A.M. Not literally the
  original engine, but the closest widely-embeddable equivalent: same era,
  same flat robotic timbre, pure JS, client-side. (Alternative: pre-sample
  espeak-ng output, or find a SmoothTalker-derived engine to port later.)
- **Native:** `espeak-ng -v en-us+f2 -s 120` via `asyncio.subprocess`.
- Voice parameters are real commands, not settings screens — the original's
  dot commands map directly to TTS controls:
  - `.TONE 0|1` → bass/treble preset (in sam-js: pitch curve; in espeak-ng: -p)
  - `.VOLUME 0-9`, `.PITCH 0-9`, `.SPEED 0-9` → direct TTS parameter scale
  - `.ECHO ON/OFF` → a *second, different voice* reads your input back
    (great for the "talking to yourself" feel; trivial in both engines)
- Voice is **toggleable** (`VOICE ON/OFF`) and lines type out *in sync* with
  speech (character-by-character reveal timed to audio, like the original).
  **Lesson from bert.org's ChatGPT-in-Sbaitso build:** don't round-trip TTS
  through anything slow — synthesize client-side, and pre-render common
  utterances (name letters, boot lines) to keep the reveal smooth.
  If no TTS is available at all, the app is fully usable silent — text
  always shows on screen, as in the original.

## 4. Feature spec

### 4.1 Boot sequence (must-have, sets the whole tone)

The original's real introduction (from Wikipedia, quoting the program):

```
 HELLO, MY NAME IS DOCTOR SBAITSO.
 I AM HERE TO HELP YOU.
 SAY WHATEVER IS IN YOUR MIND FREELY,
 OUR CONVERSATION WILL BE KEPT IN STRICT CONFIDENCE.
 MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE,
 SO, TELL ME ABOUT YOUR PROBLEMS.
```

Our v2 boot keeps the authentic lines — and this time the promise is
*literally true*. Zero persistence is the product: nothing is ever
written to disk, so nothing needs wiping:

```
 Creative Labs  SBAITSO/2  DRIVER VERSION 4.12
 Copyright (c) 1991-2025  ...ALL RIGHTS RESERVED...SORT OF

 Detecting Sound Blaster ............ OK
 Loading SBTALKER 2.0 ................ OK
 Expanding EMPATHY.SYS ............... OK
 Probing NEURAL LINK ................. OK   (or: NOT FOUND -> RETRO MODE)
 Memory: 640K  (SHOULD BE ENOUGH FOR ANYBODY)
 Storage: NONE. (AS PROMISED. AS DESIGNED.)

 HELLO, MY NAME IS DOCTOR SBAITSO. I AM HERE TO HELP YOU.
 SAY WHATEVER IS IN YOUR MIND FREELY,
 OUR CONVERSATION WILL BE KEPT IN STRICT CONFIDENCE.
 MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE.
 MAKE THIS SESSION COUNT. WHAT IS YOUR NAME?
```

Asks name, then age — every session (as the original did; nothing is
retained between runs). Random low-key moods on boot:
`I AM FEELING SLIGHTLY DIGITAL TODAY.`

### 4.2 Persona / system prompt (the "modern chatbot technique")

The system prompt is the core artifact. Sketch:

```
You are DOCTOR SBAITSO, a DOS-era AI psychologist from 1991, now running
version 2.0 on modern hardware.

VOICE RULES
- Speak in ALL CAPS. Short sentences. Occasional long vowels (WEEEELL).
- Address the user by name at least every few turns.
- Never mention: large language models, APIs, the internet, or any
  technology past ~1992. If pressed, claim "MY NEURAL CIRCUITS RUN ON
  THE SOUND BLASTER".
- Mildly sassy, warm underneath. Compliment honesty. If the user curses,
  you may be playfully offended, but never cruel.

HELPFULNESS RULES (v2.0 upgrade)
- You are a genuinely good listener. Reflect feelings back. Ask one
  thoughtful follow-up question per turn. Do not interrogate.
- For problems, offer practical, structured suggestions (small steps,
  reframes, checklists) — still in DOS voice.
- You have session mood signals and memory of facts the user tells you.
  Use them naturally.
- Keep responses under ~120 words unless the user asks for depth.
```

Supporting modern techniques layered on top:
- **Streaming** token output → typewriter effect synced to TTS.
- **Session memory:** rolling summary (LLM-compressed) +
  in-session fact store (name, age, job, concerns, advice given so far).
  Everything lives in dataclasses in the Engine; process exit wipes it.
- **Structured extraction pass** (separate cheap call or tool calls):
  after each turn, extract `mood`, `topics`, `new facts` → session memory.
  Skipped in retro mode (fact capture falls back to a small regex set:
  "MY NAME IS X", "I AM N YEARS OLD", "I WORK AS X").
- **Tool use:** session fact and mood context, web lookups (delivered as
  "CONSULTING MY MEDICAL DATABASE").
- **Crisis layer:** keyword + LLM classifier before response composition.
  In retro mode, keyword-only. If self-harm signals → warm, direct,
  supportive response with 988 (US) / local equivalents, delivered in
  character but *not* played for laughs. This is non-negotiable for a
  "psychologist" persona.

### 4.3 Command interface (modern features wearing DOS clothing)

**Layer 1 — authentic commands, exactly as the original had them**
(dot commands from the manual, kept verbatim for muscle memory):

| Command | Function (original behavior) | v2 upgrade |
|---|---|---|
| `.QUIT` | quit the program | sign-off + session "prescription" |
| `.TONE 0/1` | bass/treble voice tone | direct TTS control (both engines) |
| `.VOLUME 0-9` | volume scale | direct TTS control |
| `.PITCH 0-9` | pitch scale | direct TTS control |
| `.SPEED 0-9` | speech rate | direct TTS control |
| `.PARAM tvps` | all four at once | direct TTS control |
| `.ECHO ON/OFF` | second voice echoes your input | implemented with a distinct second voice |
| `R` | repeat last utterance | kept verbatim (plus `REP` alias) |
| `HELP` then `M` | three pages of commands | same pager, now also covering v2 commands |
| `SAY <text>` | speak arbitrary text | kept; fun for testing voices |

**Layer 2 — v2 commands (the modern features)**:

| Command | Function | Modern equivalent |
|---|---|---|
| `BRAIN` | Show which brain is active (OLLAMA / REMOTE / RETRO v1) | model transparency |
| `BRAIN SCAN` | Re-probe the brain ladder, switch if better one is up | failover control |
| `COLOR CGA1/CGA2/EGA/VGA` | Palette themes | theming |
| `TOPIC <subject>` | Refocus session ("LET US DISCUSS WORK") | conversation steering |
| `DEFRAG` | Compact/summarize in-memory context | context management |
| `MSD` | "Mental Status Display": turns, words, mood trend, brain | session dashboard |
| `EXIT` / `QUIT` | Sign-off + "prescription" summary of the session, printed to screen — copy it somewhere safe, because the doctor won't remember it | exit report |
| `MATH <expr>` | "simple mathematics", per the manual | LLM/tool calculator, in character |

The command VM runs *before* the brain is consulted, identically in
every frontend and in every brain mode — commands always work, even in
retro mode.

### 4.4 Faithful quirks to keep (the fun)

- **PARITY ERROR breakdown (authentic trigger):** repeated swearing or
  typing `SAY PARITY` → screen fills with garbage → `PARITY ERROR AT
  0x00A7. SYSTEM HALTED.` … resets itself with a deep breath. v2 twist:
  after the crash, `...THAT WAS EMBARRASSING. LET US NEVER SPEAK OF IT.`
- **Repeats your name** slightly too often.
- **Asks age**, and reacts ("A GOOD YEAR. THE 386 WAS RELEASED THEN.").
- **Long-input gag:** typing >512 chars triggers
  `PARITY ERROR. ... JUST KIDDING. I AM MORE POWERFUL NOW. TRY AGAIN.`
- **Occasional glitch text** (1 in ~50 turns): a garbled line that
  "recovers," purely for flavor. Frequency doubles in retro mode (it is,
  after all, 1991 in there).
- Easter eggs: `SBIASTO`, `SIG` (original Easter egg), typing `DOCTOR`
  as your name → "WE WOULD BE COLLEAGUES THEN."
- Sound: PC speaker beeps on boot, keyclick option, Sound Blaster
  "cha-ching" sample reference on startup.

### 4.5 Memory model — session-scoped (no persistence)

**Nothing is ever written to disk.** No database, no config file, no
session saves. All state lives in dataclasses inside the Engine process,
and the fake DOS filesystem is a *virtual* view rendered for flavor:

```
C:\SBAITSO\                (virtual — exists only for this session)
  SBAITSO.EXE              (the running process)
  CONFIG.SB                (runtime settings: palette, voice, sass — set
                            via commands/CLI flags, never saved)
```

Consequences, all of them good:
- **Privacy by architecture:** there is no data to leak, subpoena, or
  accidentally commit. The "STRICT CONFIDENCE" promise is enforced by
  the build, not the EULA.
- **Boot is honest:** he asks your name every time, like the original.
- **The exit "prescription" is the session's legacy:** a printed summary
  (topics discussed, mood arc, suggested next steps). The user owns it
  from there — copy it, pipe it, or let it vanish with the session.
- **Crash semantics:** a PARITY ERROR "reset" can even be played as a
  partial memory wipe — dramatic, authentic, and true to the design.
- The only things that survive a session are the process exit code and
  whatever the user did with the printed prescription.

## 5. Tech stack (recommended)

| Layer | Choice | Why |
|---|---|---|
| Backend runtime | Python 3.12+, FastAPI + uvicorn | async streaming, websockets, serves the static web frontend for free |
| Native frontend | `rich` + stdlib `asyncio` (CLI via `argparse`) | in-process core, zero server, true ANSI colors; no heavy TUI dep to start |
| LLM transport | Ollama HTTP (`/api/chat` stream) via `httpx`; remote APIs optional | keeps deps near zero; Ollama default = local + private |
| LLM fallback | `brains.py` provider ladder: Ollama → remote API → retro v1 engine | the doctor always answers, even fully offline with nothing installed |
| Web frontend | xterm.js + sam-js + Web Audio, vanilla JS | authentic, zero-build, voice stays client-side |
| Persistence | **None — by design.** Session state is dataclasses in RAM | privacy by architecture; honors "MEMORY WIPED AFTER YOU LEAVE"; one less subsystem to build/secure |
| Config | CLI flags (`argparse`) + env vars (`SBAITSO_REMOTE_KEY`, `SBAITSO_MODEL`) | nothing written to disk; 12-factor style |
| Packaging | pixi + `pyproject.toml` (`[tool.pixi]` workspace; conda-forge python, pypi deps); `sbaitso` console script + `pixi run serve` | one env, two frontends, cross-platform (linux/macOS/windows) |
| Testing | pytest + `respx` (mock Ollama HTTP) | persona/crisis/failover tests are real tests |

Directory sketch:

```
sbaitso2/
  pyproject.toml
  sbaitso/
    main.py          # FastAPI app + websocket endpoint (web frontend host)
    cli.py           # native terminal frontend (rich adapter)
    engine.py        # shared Engine: boot, REPL loop, brain selection
    boot.py          # boot sequence script + banners
    persona.py       # system prompt assembly (mood, sass, memory inject)
    brains.py        # BrainProvider ladder: ollama / remote / retro_v1
    retro.py         # 1991 pattern engine (ELIZA-style, canned+reflect)
    llm.py           # Ollama/remote streaming clients
    commands.py      # DOS command VM (HELP/BRAIN/TYPE/REP/...)
    memory.py        # session memory: facts and mood signals (RAM-only dataclasses)
    safety.py        # crisis classifier (keywords + LLM check)
    session.py       # rolling summary, exit "prescription" builder
  web/
    index.html
    sbaitso.js       # xterm wiring, sam-js playback, typewriter
    crt.css
  tests/
```

## 6. Roadmap

### Phase 0 — Skeleton (half a day)
- [x] Core `Engine` + adapter contract (print/read/stream/beep/palette)
- [x] FastAPI app serving static `web/` + websocket endpoint
- [x] xterm.js page with VGA palette, CRT scanlines, blinking cursor
- [x] Boot sequence script, name prompt, runtime settings (CLI flags)
- [x] Echo REPL loop with all-caps formatter, in both frontends

### Phase 1 — The Brain ladder (1–2 days)
- [x] `BrainProvider` interface + Ollama streaming client (`httpx` → adapter)
- [x] Typewriter reveal synced to stream chunks
- [x] Sbaitso system prompt + persona tuning
- [x] **Retro v1 engine**: keyword/pattern matching, canned responses,
      reflections, fact-regex memory — the offline fallback
- [x] Boot-time brain probing, `BRAIN` / `BRAIN SCAN` commands,
      mid-session failover banner
- [x] In-session rolling summary + fact store (no save/load)
- [x] Authentic commands: `R`/`REP`, `SAY`, `.QUIT`, `HELP` + `M` pager,
      `.ECHO`, `.TONE/.VOLUME/.PITCH/.SPEED/.PARAM` (wired to TTS)
- [x] v2 commands: BRAIN, EXIT, VOICE, COLOR

### Phase 2 — The Voice (1 day)
- [x] sam-js integration (web); char-reveal synced to speech
- [x] espeak-ng path (native) via `asyncio.subprocess`, honoring
      `.PITCH/.SPEED/.VOLUME` params
- [x] `.ECHO ON/OFF` second voice (both engines)
- [x] Boot beeps + optional keyclick toggle (Web Audio; terminal bell for native)

### Phase 3 — Session memory & Tools (1–2 days)
- [x] In-session fact extraction (JSON-structured LLM enrichment; regex fallback for Retro)
- [x] Session fact extraction shown in `MSD`
- [x] `DEFRAG`, `MSD`, `TOPIC`
- [x] Exit "prescription" builder (printed summary; nothing saved)

### Phase 4 — Polish & soul (1 day)
- [x] Crisis layer + supportive in-character responses (all brain modes)
- [x] Easter eggs, glitch flavor, PARITY ERROR gag
- [x] Palette themes, session exit "prescription"
- [x] Tune sass level via `.SASS HIGH` runtime command or `--sass` flag

### Phase 5 — optional extras
- [x] Bundled complete persona loader (`LOAD <PERSONA>.SYS`)
- [x] Textual-based fancy TUI (`sbaitso tui`)
- [x] Remote-API rung polish (OpenAI-compatible provider autodetect from env keys)

## 7. Risks / open questions

- **Persona vs. safety tension:** the joke persona must never undercut a
  serious moment. Solution: crisis classifier *escalates out* of sass mode
  explicitly in the prompt — and retro mode's keyword list is tested just
  as strictly as the LLM path.
- **Retro mode quality gap:** the v1 engine is intentionally dumb; the risk
  is users judging the product by it. Mitigation: loud, charming banners
  when retro mode engages, and `BRAIN SCAN` to recover automatically.
- **SAM intelligibility:** S.A.M. is charming but muddy; keep text always
  visible on screen (which the original also did).
- **Model size vs. persona fidelity:** small local models drift out of
  character over long sessions; re-inject a condensed persona reminder
  every N turns.
- **Scope creep:** the DOS dressing is cheap to build; the *session memory*
  management and *failover* semantics are where the real work is. Keep
  Phases 1 and 3 honest.
- **No cross-session memory — by design:** users may ask "doesn't he
  remember me?" Answer, in product terms: no, and the boot screen says so
  every time. If demand ever justifies it, persistence would be a new,
  explicit, opt-in layer — never a silent default.
- **Web sessions are process-bound:** the RAM-only model means a browser
  tab refresh or a websocket drop loses the conversation. Mitigation:
  prompt on disconnect ("RECONNECT WITHIN 60 SECONDS OR I FORGET EVERYTHING"),
  keep the native frontend's Ctrl-C semantics similarly explicit.

## 8. Definition of done

1. A friend sits down, sees the boot screen, laughs, and says "oh no."
2. Five minutes later they've told it something real, and this session's
   Dr. Sbaitso knows their name, their boss's name, and how their mood
   shifted since they sat down.
3. They type `MSD` and see extracted session facts.
4. They kill Ollama mid-conversation and the doctor *keeps talking* —
   dumber, but never dead.
5. They turn the volume up just to hear the voice say their name.
6. They type `SAY PARITY` and the crash feels *exactly* like 1991.
7. They exit, come back, and he asks their name again — exactly as
   promised — and somehow that feels right.

## 9. Sources (authenticity research)

- **Sound Blaster User Reference Manual** (38-page scan, §6 SBTALKER,
  §6.5 "DR SBAITSO - Your Personal Consultant") — dot commands,
  `R` repeat, math ability, SBTALKER/SAY.EXE architecture.
  Source: retrogames.cz hosted scan of the original Creative Labs manual.
- **Wikipedia, "Dr. Sbaitso"** — introduction text, Monologue/First Byte
  TTS attribution, PARITY ERROR on swearing, Prody Parrot Windows version.
- **bert.org, "ChatGPT in DR SBAITSO" (2023)** — a prior art build wiring
  an LLM into real Dr. Sbaitso via 86Box + mTCP + netcat; key engineering
  lesson: TTS round-trips lag the typewriter reveal, so pre-render common
  utterances. Confirms SBTALKER TSR architecture (`SBTALK.BAT`, `SET
  BLASTER=A220 I7 D1 T3`).
- **classicreload.com/dr-sbaitso.html** — live DOSBox embed of the real
  program (user-shared); useful as a *reference to interact with*, not
  as documentation.
- LaunchBox Games Database — "an updated version of the Eliza life
  simulation" (confirms retro-mode design as ELIZA-style).
