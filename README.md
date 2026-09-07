# DR. SBAITSO/2

> "HELLO, MY NAME IS DOCTOR SBAITSO. I AM HERE TO HELP YOU."

A modern recreation of Creative Labs' 1991 DOS psychologist — same boot
screen, same ALL CAPS, same monotone soul, same PARITY ERROR — with a real
brain (local LLM), a 1991 fallback brain, session memory, and **zero
persistence**: memory is rich within a session and wiped when you leave,
exactly as the original promised.

## Quickstart (with [pixi](https://pixi.sh))

```sh
pixi run sbaitso            # native terminal frontend
pixi run sbaitso tui        # fullscreen Textual frontend
pixi run serve              # web frontend at http://127.0.0.1:8000
pixi run test               # run the test suite
```

Both frontends share one core and behave identically. Task args pass
through: `pixi run serve --port 8321`.

## The brain ladder

1. **Ollama** (default, local): probed at boot via `/api/tags`.
2. **Remote API** (optional): use explicit `SBAITSO_REMOTE_KEY` / `--remote-key`
   settings, or automatically detect a supported OpenAI-compatible provider key.
3. **RETRO v1** (always): a faithful 1991 pattern-matching engine. If no
   LLM is reachable, Dr. Sbaitso degrades — never dies:

   ```
    WARNING: NEURAL LINK LOST.
    SWITCHING TO 1991 COMPATIBILITY MODE.
    I AM ONLY AS SMART AS I WAS THEN. BE PATIENT WITH ME.
   ```

Useful flags: `--brain auto|retro|ollama|remote`, `--model NAME`,
`--persona PERSONA`, `--sass LOW|NORMAL|HIGH`, `--color CGA1|CGA2|EGA|VGA|AMBER`.
`--persona` is case-insensitive and extensionless; its help text lists the
personas bundled with the installed package.
Only `--brain auto` uses the fallback ladder; an explicitly requested
`ollama` or `remote` brain exits with an error if it cannot be reached.

Remote setting precedence is CLI flags, then `SBAITSO_REMOTE_KEY`,
`SBAITSO_REMOTE_URL`, and `SBAITSO_REMOTE_MODEL`, then the first detected
provider key. Supported autodetected OpenAI-compatible provider variables are
`OPENAI_API_KEY`, `GROQ_API_KEY`, `TOGETHER_API_KEY`, `OPENROUTER_API_KEY`,
`MISTRAL_API_KEY`, and `CEREBRAS_API_KEY`. Ollama remains the preferred
healthy brain in automatic mode.
In the native frontend, `--debug-llm` prints the outbound JSON request,
escaped inbound response chunks, time to first chunk, and total stream time
for Ollama or remote calls (messages and model only; never authorization
headers).

## Commands

Authentic (from the 1991 manual): `.QUIT`, `.TONE 0|1`,
`.VOLUME 0-9`, `.PITCH 0-9`, `.SPEED 0-9`, `.PARAM tvps`, `.ECHO ON/OFF`,
`R` (repeat), `SAY <text>`, `HELP` (then `M` for pages 2 and 3).

Version 2.0: `BRAIN`, `BRAIN SCAN`, `BRAIN RETRO`, `PATIENT LLM [N]`, `VOICE ON|OFF`,
`TOPIC <subject>`, `DEFRAG`, `MSD`, `MATH <expr>`, `COLOR <name>`,
`LOAD [PERSONA].SYS`, `.SASS LOW|NORMAL|HIGH`, `.KEYCLICK ON|OFF`, `EXIT`.

## Personas

The bundled `sbaitso.sys` persona loads by default. `LOAD` with no argument
lists all bundled personas; `LOAD GENTLE.SYS` replaces the complete active
persona for the RAM-only session. Persona resources are discovered dynamically
from `sbaitso/personas/*.sys`, not from an application hardcoded list. Only
those bundled package resources can be loaded—`LOAD` never reads an arbitrary
user path.

A persona may start with `NAME: <name>` followed by a blank line. That name is
used by the boot greeting (`HELLO, MY NAME IS ...`). If the header is absent,
the uppercase filename stem is used instead. The currently bundled personas
are `SBAITSO.SYS` (DOCTOR SBAITSO), `GENTLE.SYS` (LUCY), and `SARDONIC.SYS`
(MAX). Resource filenames are lowercase; the DOS interfaces display them in
uppercase.

Try `SAY PARITY` for an authentic crash. `PATIENT LLM` defaults to 8 turns;
an explicit count may be from 1 to 256 turns.

## Voice

- **Web:** uses the bundled `sam-js` S.A.M. synthesizer. LLM text streams to
  the display in partial chunks, word-wrapping to the available terminal
  width; once a sentence closes, it is synthesized as one utterance. Complete
  non-streamed lines reveal at the generated audio pace. Browser audio unlocks
  after a click or keypress; entering your name does it.
- **Native:** uses `espeak-ng` automatically when it is installed and on
  `PATH`; otherwise text mode continues silently. Pass `--novoice` to disable
  it deliberately.
- The authentic `.TONE`, `.VOLUME`, `.PITCH`, `.SPEED`, `.PARAM`, and
  `.ECHO ON/OFF` commands drive both voice backends. `VOICE ON` / `VOICE OFF`
  toggles synthesis without changing those settings.

## Development

```sh
pixi install               # create .pixi env (conda-forge python + pypi deps)
pixi run test              # run tests (offline; Ollama probing is redirected)
```

## License & credits

Dr. Sbaitso was © Creative Labs, 1991. This is an affectionate fan
recreation. The 1991 manual scan in this folder is reference material,
kept locally and not tracked in git.

The bundled `web/vendor/samjs.min.js` is SamJs v0.3.1, © 2017–2024
Christian Schiffler / [discordier/sam](https://github.com/discordier/sam),
a reverse-engineered JavaScript port of Software Automatic Mouth. Its
copyright header is retained; upstream describes the underlying original as
abandonware and says to use it at your own risk.
