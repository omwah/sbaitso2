/* DR. SBAITSO/2 — web frontend
 * xterm.js terminal + websocket to the Python core.
 * Voice: sam-js (S.A.M. port) — the typewriter reveal is paced to the
 * synthesized speech, like the original.
 */

"use strict";

const PALETTES = {
  cga1:  { background: "#0000aa", foreground: "#55ffff", cursor: "#55ffff",
           brightBlack: "#5555ff" },
  cga2:  { background: "#000000", foreground: "#55ff55", cursor: "#55ff55",
           brightBlack: "#225522" },
  ega:   { background: "#000055", foreground: "#ffffff", cursor: "#ffffff",
           brightBlack: "#6666aa" },
  vga:   { background: "#0a0a0a", foreground: "#c8c8c8", cursor: "#c8c8c8",
           brightBlack: "#555555" },
  amber: { background: "#0a0500", foreground: "#ffb000", cursor: "#ffb000",
           brightBlack: "#663300" },
};

const COLORS = {
  white: "\x1b[97m", cyan: "\x1b[96m", yellow: "\x1b[93m",
  green: "\x1b[92m", red: "\x1b[91m", dim: "\x1b[90m",
};
const RESET = "\x1b[0m";

const term = new window.Terminal({
  cursorBlink: true,
  fontFamily: '"IBM Plex Mono", "DejaVu Sans Mono", "Courier New", monospace',
  fontSize: 16,
  scrollback: 4000,
  convertEol: true,
  theme: PALETTES.cga1,
});
const fitAddon = new window.FitAddon.FitAddon();
term.loadAddon(fitAddon);
term.open(document.getElementById("terminal"));
fitAddon.fit();
window.addEventListener("resize", () => fitAddon.fit());

let sayColor = COLORS.cyan;
let inputEnabled = false;
let inputBuffer = "";
let dead = false;

/* ---- voice state: the authentic 0-9 scales, mapped to S.A.M. ---- */
const SAM_RATE = 22050;
const voice = { on: true, tone: 1, volume: 5, pitch: 5, speed: 5 };

function samParams(echo) {
  // .PITCH 0-9 -> sam pitch ~20..100 (default 5 ~= 65, close to S.A.M.'s 64)
  // .SPEED 0-9 -> sam speed ~50..95  (default 5 ~= 75, near S.A.M.'s 72)
  const pitch = echo ? 100 + voice.pitch * 6 : 20 + voice.pitch * 9;
  const speed = echo ? 90 + voice.speed * 4 : 50 + voice.speed * 5;
  // .TONE 0=bass / 1=treble -> formant presets
  let mouth = 128, throat = 128;
  if (!echo) {
    if (voice.tone === 0) { mouth = 110; throat = 190; }  // bass
    else                  { mouth = 150; throat = 110; }  // treble
  } else {
    mouth = 170; throat = 90;  // the .ECHO second voice: distinct & nasal
  }
  return { pitch, speed, mouth, throat };
}

let audioCtx = null;
function getAudioCtx() {
  if (!audioCtx) {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) { return null; }
    if (audioCtx.state === "suspended") {
      const resume = () => { audioCtx.resume(); };
      window.addEventListener("keydown", resume, { once: true });
      window.addEventListener("mousedown", resume, { once: true });
      window.addEventListener("touchstart", resume, { once: true });
    }
  }
  return audioCtx;
}

/* Browsers gate audio behind a user gesture. The boot beeps usually miss
 * the gate; conversation speech lands after the user has typed their name,
 * so it plays. */
function beep(freq, ms) {
  const ctx = getAudioCtx();
  if (!ctx || ctx.state !== "running") return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square";
    osc.frequency.value = freq;
    gain.gain.value = 0.05;
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start();
    setTimeout(() => osc.stop(), ms);
  } catch (e) {}
}

/* Synthesize + play; returns the spoken duration in seconds (0 if silent). */
function speak(text, echo) {
  if (!voice.on || typeof window.SamJs !== "function") return 0;
  const ctx = getAudioCtx();
  if (!ctx || ctx.state !== "running") return 0;
  try {
    const sam = new window.SamJs(samParams(echo));
    const f32 = sam.buf32(text);
    if (!f32 || !f32.length) return 0;
    const buffer = ctx.createBuffer(1, f32.length, SAM_RATE);
    buffer.getChannelData(0).set(f32);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const gain = ctx.createGain();
    gain.gain.value = Math.min(1.0, (voice.volume / 9) * 0.9);
    src.connect(gain); gain.connect(ctx.destination);
    src.start();
    return f32.length / SAM_RATE;
  } catch (e) { return 0; }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---- event queue (preserves order while typing) ---- */
const queue = [];
let pumping = false;

function enqueue(ev) {
  queue.push(ev);
  pump();
}

async function pump() {
  if (pumping) return;
  pumping = true;
  while (queue.length > 0) {
    const ev = queue.shift();
    await handle(ev);
  }
  pumping = false;
}

async function handle(ev) {
  switch (ev.type) {
    case "line":
      if (ev.delay_ms) await sleep(ev.delay_ms);
      term.write((COLORS[ev.color] || "") + ev.text + RESET + "\r\n");
      break;
    case "say": {
      if (ev.delay_ms) await sleep(ev.delay_ms);
      const echo = ev.voice === "echo";
      const duration = speak(ev.text, echo);
      await typeOut(ev.text, ev.reveal, echo, duration);
      break;
    }
    case "beep":
      beep(ev.freq, ev.ms);
      if (ev.delay_ms) await sleep(ev.delay_ms);
      break;
    case "bell":
      term.bell();
      break;
    case "palette":
      term.options.theme = PALETTES[ev.name] || PALETTES.cga1;
      sayColor = { cga1: COLORS.cyan, cga2: COLORS.green, ega: COLORS.white,
                   vga: COLORS.white, amber: COLORS.yellow }[ev.name] || COLORS.cyan;
      document.body.style.background =
        (PALETTES[ev.name] || PALETTES.cga1).background;
      break;
    case "clear":
      term.clear();
      break;
    case "prompt": {
      const label = (ev.label || "YOU").toUpperCase();
      term.write("\r\n" + COLORS.dim + label + "> " + RESET);
      inputEnabled = true;
      break;
    }
    case "voiceparams":
      if (ev.tone !== null && ev.tone !== undefined) voice.tone = ev.tone;
      if (ev.volume !== null && ev.volume !== undefined) voice.volume = ev.volume;
      if (ev.pitch !== null && ev.pitch !== undefined) voice.pitch = ev.pitch;
      if (ev.speed !== null && ev.speed !== undefined) voice.speed = ev.speed;
      break;
    case "voiceenabled":
      voice.on = ev.on;
      break;
    case "echomode":
      break;
    case "quit":
      inputEnabled = false;
      dead = true;
      if (ev.error) {
        term.write("\r\n" + COLORS.red +
          " STARTUP FAILED. THE REQUESTED BRAIN IS UNAVAILABLE.\r\n" +
          " REFRESH AFTER CORRECTING THE BRAIN CONFIGURATION.\r\n" + RESET);
      } else {
        term.write("\r\n" + COLORS.yellow +
          " SESSION ENDED. AS PROMISED, I REMEMBER NOTHING.\r\n" +
          " REFRESH THE PAGE TO BEGIN ANEW.\r\n" + RESET);
      }
      try { ws.close(); } catch (e) {}
      break;
    default:
      break;
  }
}

async function typeOut(text, reveal, echoVoice, spokenSec) {
  const color = echoVoice ? COLORS.dim : sayColor;
  term.write(color);
  if (reveal) {
    // pace the reveal to the speech, clamped to sane typewriter speeds
    let perChar = 14;
    if (spokenSec > 0 && text.length > 0) {
      perChar = Math.min(45, Math.max(6, (spokenSec * 1000) / text.length));
    }
    for (const ch of text) {
      term.write(ch);
      await sleep(perChar);
    }
  } else {
    term.write(text);
  }
  term.write(RESET + "\r\n");
  // let longer utterances finish before the next line starts
  if (spokenSec > 0) {
    const typed = (reveal ? perChar * text.length : 0) / 1000;
    if (spokenSec > typed) await sleep((spokenSec - typed) * 1000);
  }
}

/* ---- input ---- */
term.onData((data) => {
  if (!inputEnabled || dead) return;
  for (const ch of data) {
    if (ch === "\r") {
      const line = inputBuffer;
      inputBuffer = "";
      inputEnabled = false;
      term.write("\r\n");
      send(line);
    } else if (ch === "\u007f") {
      if (inputBuffer.length > 0) {
        inputBuffer = inputBuffer.slice(0, -1);
        term.write("\b \b");
      }
    } else if (ch >= " ") {
      inputBuffer += ch;
      term.write(ch);
    }
  }
});

function send(text) {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ type: "input", text }));
  }
}

/* ---- websocket ---- */
let ws = null;
function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(proto + "//" + location.host + "/ws");
  ws.onmessage = (e) => {
    try { enqueue(JSON.parse(e.data)); } catch (err) {}
  };
  ws.onclose = () => {
    if (!dead) {
      term.write("\r\n\x1b[91m CONNECTION LOST. REFRESH TO TRY AGAIN.\x1b[0m\r\n");
    }
  };
}
connect();
