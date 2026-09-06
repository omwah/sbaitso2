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
  amber: {
    background: "#160400", foreground: "#ffb347", cursor: "#ffd36b",
    black: "#260700", red: "#ff7a24", green: "#ff9a3d", yellow: "#ffc35a",
    blue: "#b95a1b", magenta: "#e07025", cyan: "#ffb347", white: "#ffd18a",
    brightBlack: "#7a3515", brightRed: "#ff8a32", brightGreen: "#ffad4d",
    brightYellow: "#ffd36b", brightBlue: "#d76a22", brightMagenta: "#f08a35",
    brightCyan: "#ffd18a", brightWhite: "#ffe0a3",
  },
};

const COLORS = {
  white: "\x1b[97m", cyan: "\x1b[96m", yellow: "\x1b[93m",
  green: "\x1b[92m", red: "\x1b[91m", dim: "\x1b[90m",
};
const RESET = "\x1b[0m";
const RESPONSE_INDENT = " ";  // match the boot banner's one-character gutter
const RESPONSE_RIGHT_GUTTER_COLUMNS = 3;
const SAY_WRAP_WIDTH = 72;
let sayColumn = 0;
let sayWord = "";

const term = new window.Terminal({
  cursorBlink: true,
  fontFamily: '"IBM Plex Mono", "DejaVu Sans Mono", "Courier New", monospace',
  fontSize: 16,
  scrollback: 4000,
  convertEol: true,
  theme: PALETTES.vga,
});
const fitAddon = new window.FitAddon.FitAddon();
term.loadAddon(fitAddon);
term.open(document.getElementById("terminal"));
fitAddon.fit();
// xterm attaches its textarea during open(); wait one frame before focusing it.
requestAnimationFrame(() => term.focus());
window.addEventListener("resize", () => fitAddon.fit());

let followFrame = 0;
function followOutput() {
  if (followFrame) return;
  followFrame = requestAnimationFrame(() => {
    followFrame = 0;
    term.scrollToBottom();
  });
}
function writeOutput(text) {
  term.write(text);
  followOutput();
}

function wrapTerminalLine(text) {
  const width = Math.max(1, term.cols || SAY_WRAP_WIDTH);
  const indent = (text.match(/^\s*/) || [""])[0];
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return indent;
  const lines = [];
  let line = indent;
  for (const word of words) {
    const hasWord = line.length > indent.length;
    if (hasWord && line.length + 1 + word.length > width) {
      lines.push(line);
      line = indent + word;
    } else {
      line += (hasWord ? " " : "") + word;
    }
  }
  lines.push(line);
  return lines.join("\r\n");
}

let sayColor = COLORS.white;
let inputEnabled = false;
let inputBuffer = "";
let dead = false;

/* ---- voice state: the authentic 0-9 scales, mapped to S.A.M. ---- */
const SAM_RATE = 22050;
const voice = { on: true, tone: 1, volume: 5, pitch: 5, speed: 5 };
const controlsToggle = document.getElementById("controls-toggle");
const controlDrawer = document.getElementById("control-drawer");
const voiceToggle = document.getElementById("voice-toggle");
const voiceControls = {
  tone: document.getElementById("tone-control"),
  volume: document.getElementById("volume-control"),
  pitch: document.getElementById("pitch-control"),
  speed: document.getElementById("speed-control"),
};
const voiceValues = {
  tone: document.getElementById("tone-value"),
  volume: document.getElementById("volume-value"),
  pitch: document.getElementById("pitch-value"),
  speed: document.getElementById("speed-value"),
};
function setControlsOpen(open) {
  controlDrawer.hidden = !open;
  controlDrawer.classList.toggle("open", open);
  controlDrawer.setAttribute("aria-hidden", String(!open));
  controlsToggle.setAttribute("aria-expanded", String(open));
  if (!open) term.focus();
}

controlsToggle.addEventListener("click", () => {
  setControlsOpen(controlDrawer.hidden);
});

let controlKeyUsed = false;
document.addEventListener("keydown", (event) => {
  if (event.key === "Control") {
    controlKeyUsed = false;
    return;
  }
  if (event.ctrlKey) controlKeyUsed = true;
  if (event.key === "Escape" && controlDrawer.classList.contains("open")) {
    event.preventDefault();
    setControlsOpen(false);
  }
});

document.addEventListener("keyup", (event) => {
  if (event.key === "Control" && !controlKeyUsed) {
    setControlsOpen(controlDrawer.hidden);
  }
});

function syncVoiceToggle() {
  voiceToggle.setAttribute("aria-checked", String(voice.on));
  voiceToggle.setAttribute(
    "aria-label", voice.on ? "Disable speech synthesis" : "Enable speech synthesis"
  );
}

voiceToggle.addEventListener("click", () => {
  voice.on = !voice.on;
  if (!voice.on) stopActiveSpeech();
  syncVoiceToggle();
  setControlsOpen(false);
});

function syncVoiceControls() {
  for (const [name, control] of Object.entries(voiceControls)) {
    control.value = voice[name];
    voiceValues[name].textContent = name === "tone"
      ? (voice.tone === 0 ? "BASS" : "TREBLE")
      : voice[name];
  }
}

for (const [name, control] of Object.entries(voiceControls)) {
  control.addEventListener("input", () => {
    voice[name] = Number(control.value);
    syncVoiceControls();
  });
}

syncVoiceControls();

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
const activeSpeech = new Set();

function stopActiveSpeech() {
  for (const source of activeSpeech) {
    try { source.stop(); } catch (e) {}
  }
  activeSpeech.clear();
}

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
    src.onended = () => activeSpeech.delete(src);
    activeSpeech.add(src);
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
      const text = ev.wrap ? wrapTerminalLine(ev.text) : ev.text;
      writeOutput((COLORS[ev.color] || "") + text + RESET + "\r\n");
      sayColumn = 0;
      sayWord = "";
      break;
    case "say": {
      if (ev.delay_ms) await sleep(ev.delay_ms);
      const echo = ev.voice === "echo";
      const spokenText = ev.speech_text || ev.text;
      const duration = ev.partial ? 0 : speak(spokenText, echo);
      await typeOut(
        ev.text, ev.reveal, echo, duration, ev.partial, ev.line_end !== false
      );
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
      document.body.classList.toggle("amber-display", ev.name === "amber");
      break;
    case "clear":
      term.clear();
      followOutput();
      sayColumn = 0;
      sayWord = "";
      break;
    case "prompt": {
      const label = (ev.label || "YOU").toUpperCase();
      writeOutput("\r\n" + RESPONSE_INDENT + COLORS.dim + label + "> " + RESET);
      sayColumn = 0;
      sayWord = "";
      inputEnabled = true;
      break;
    }
    case "voiceparams":
      if (ev.tone !== null && ev.tone !== undefined) voice.tone = ev.tone;
      if (ev.volume !== null && ev.volume !== undefined) voice.volume = ev.volume;
      if (ev.pitch !== null && ev.pitch !== undefined) voice.pitch = ev.pitch;
      if (ev.speed !== null && ev.speed !== undefined) voice.speed = ev.speed;
      syncVoiceControls();
      break;
    case "voiceenabled":
      voice.on = ev.on;
      if (!voice.on) stopActiveSpeech();
      syncVoiceToggle();
      break;
    case "echomode":
      break;
    case "quit":
      inputEnabled = false;
      dead = true;
      if (ev.error) {
        writeOutput("\r\n" + COLORS.red +
          " STARTUP FAILED. THE REQUESTED BRAIN IS UNAVAILABLE.\r\n" +
          " REFRESH AFTER CORRECTING THE BRAIN CONFIGURATION.\r\n" + RESET);
      } else {
        writeOutput("\r\n" + COLORS.yellow +
          " SESSION ENDED. AS PROMISED, I REMEMBER NOTHING.\r\n" +
          " REFRESH THE PAGE TO BEGIN ANEW.\r\n" + RESET);
      }
      try { ws.close(); } catch (e) {}
      break;
    default:
      break;
  }
}

function ensureResponseIndent() {
  if (sayColumn === 0) {
    writeOutput(RESPONSE_INDENT);
    sayColumn = RESPONSE_INDENT.length;
  }
}

async function writeSayChar(ch, reveal, perChar) {
  writeOutput(ch);
  sayColumn += 1;
  if (reveal) await sleep(perChar);
}

function currentWrapWidth() {
  // Match the CLI's 72-column response width, while FitAddon still reduces
  // it for a narrow viewport and preserves the visible right-side gutter.
  return Math.max(
    1,
    Math.min(SAY_WRAP_WIDTH, (term.cols || SAY_WRAP_WIDTH) - RESPONSE_RIGHT_GUTTER_COLUMNS)
  );
}

async function flushSayWord(reveal, perChar) {
  if (!sayWord) return;
  let wrapWidth = currentWrapWidth();
  if (sayColumn && sayColumn + sayWord.length > wrapWidth) {
    writeOutput("\r\n");
    sayColumn = 0;
  }
  ensureResponseIndent();
  for (const ch of sayWord) {
    wrapWidth = currentWrapWidth();
    if (sayColumn >= wrapWidth) {
      writeOutput("\r\n");
      sayColumn = 0;
      ensureResponseIndent();
    }
    await writeSayChar(ch, reveal, perChar);
  }
  sayWord = "";
}

async function writeWrappedText(text, reveal, perChar) {
  for (const ch of text) {
    if (ch === "\n") {
      await flushSayWord(reveal, perChar);
      if (sayColumn) {
        writeOutput("\r\n");
        sayColumn = 0;
      }
    } else if (/\s/.test(ch)) {
      await flushSayWord(reveal, perChar);
      if (sayColumn < currentWrapWidth()) await writeSayChar(ch, reveal, perChar);
    } else {
      sayWord += ch;
    }
  }
}

async function typeOut(
  text, reveal, echoVoice, spokenSec, partial = false, lineEnd = true
) {
  const color = echoVoice ? COLORS.dim : sayColor;
  writeOutput(color);
  let perChar = 14;
  // Complete sentences pace to speech. Streamed partial text remains brisk
  // so the user sees model progress instead of waiting for a period.
  if (reveal && !partial && spokenSec > 0 && text.length > 0) {
    perChar = Math.min(45, Math.max(6, (spokenSec * 1000) / text.length));
  }
  await writeWrappedText(text, reveal, perChar);
  if (lineEnd) await flushSayWord(reveal, perChar);
  writeOutput(RESET);
  if (lineEnd && sayColumn) {
    writeOutput("\r\n");
    sayColumn = 0;
  }
  // Let longer utterances finish before the next line starts.
  if (!partial && spokenSec > 0) {
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
      writeOutput("\r\n\x1b[91m CONNECTION LOST. REFRESH TO TRY AGAIN.\x1b[0m\r\n");
    }
  };
}
connect();
