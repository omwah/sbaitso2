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
pixi run serve              # web frontend at http://127.0.0.1:8000
pixi run test               # run the test suite
```

Both frontends share one core and behave identically. Task args pass
through: `pixi run serve --port 8321`.

## The brain ladder

1. **Ollama** (default, local): probed at boot via `/api/tags`.
2. **Remote API** (optional): set `SBAITSO_REMOTE_KEY` (OpenAI-compatible).
3. **RETRO v1** (always): a faithful 1991 pattern-matching engine. If no
   LLM is reachable, Dr. Sbaitso degrades — never dies:

   ```
    WARNING: NEURAL LINK LOST.
    SWITCHING TO 1991 COMPATIBILITY MODE.
    I AM ONLY AS SMART AS I WAS THEN. BE PATIENT WITH ME.
   ```

Useful flags: `--brain auto|retro|ollama|remote`, `--model NAME`,
`--sass LOW|NORMAL|HIGH`, `--palette CGA1|CGA2|EGA|VGA|AMBER`, `--doshell`.
Only `--brain auto` uses the fallback ladder; an explicitly requested
`ollama` or `remote` brain exits with an error if it cannot be reached.
In the native frontend, `--debug-llm` prints the outbound JSON request for
Ollama or remote calls (messages and model only; never authorization headers).

## Commands

Authentic (from the 1991 manual): `.QUIT`, `.READ <file>`, `.TONE 0|1`,
`.VOLUME 0-9`, `.PITCH 0-9`, `.SPEED 0-9`, `.PARAM tvps`, `.ECHO ON/OFF`,
`R` (repeat), `SAY <text>`, `HELP` (then `M` for pages 2 and 3).

Version 2.0: `BRAIN`, `BRAIN SCAN`, `VOICE ON|OFF`, `DIR`, `TYPE MEMORY.DAT`,
`MOOD`, `TOPIC <subject>`, `DEFRAG`, `MSD`, `MATH <expr>`, `COLOR <name>`,
`DOSSHELL <cmd>` (if enabled), `EXIT`.

Try `SAY PARITY` for an authentic crash.

## Voice

- **Web:** uses the bundled `sam-js` S.A.M. synthesizer. Speech is queued
  line-by-line, and the typewriter reveal is paced to the generated audio.
  Browser audio unlocks after a click or keypress; entering your name does it.
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

## Status

Phase 0–2 complete (see `PLAN.md`): core engine, both frontends, brain
ladder with failover, command VM, session memory (RAM only), safety layer,
PARITY ERROR theater, and synchronized web/native voice backends.

Phase 3 polish and Phase 4 extras remain.

## License & credits

Dr. Sbaitso was © Creative Labs, 1991. This is an affectionate fan
recreation. The 1991 manual scan in this folder is reference material,
kept locally and not tracked in git.

The bundled `web/vendor/samjs.min.js` is SamJs v0.3.1, © 2017–2024
Christian Schiffler / [discordier/sam](https://github.com/discordier/sam),
a reverse-engineered JavaScript port of Software Automatic Mouth. Its
copyright header is retained; upstream describes the underlying original as
abandonware and says to use it at your own risk.
