/* DR. SBAITSO/2 — web frontend
 * xterm.js terminal + websocket to the Python core.
 * Handles the Engine event stream: boot pacing, typewriter reveal,
 * PC-speaker beeps, palette switching.
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

/* ---- audio: PC speaker emulation ---- */
let audioCtx = null;
function beep(freq, ms) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "square";
    osc.frequency.value = freq;
    gain.gain.value = 0.05;
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    setTimeout(() => { osc.stop(); }, ms);
  } catch (e) { /* audio blocked until user gesture; fine */ }
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
    case "say":
      if (ev.delay_ms) await sleep(ev.delay_ms);
      await typeOut(ev.text, ev.reveal, ev.voice);
      break;
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
    case "prompt":
      const label = (ev.label || "YOU").toUpperCase();
      term.write("\r\n" + COLORS.dim + label + "> " + RESET);
      inputEnabled = true;
      break;
    case "voiceparams":
    case "echomode":
      break; /* Phase 2: sam-js honors these */
    case "quit":
      inputEnabled = false;
      dead = true;
      term.write("\r\n" + COLORS.yellow +
        " SESSION ENDED. AS PROMISED, I REMEMBER NOTHING.\r\n" +
        " REFRESH THE PAGE TO BEGIN ANEW.\r\n" + RESET);
      try { ws.close(); } catch (e) {}
      break;
    default:
      break;
  }
}

async function typeOut(text, reveal, voice) {
  const color = voice === "echo" ? COLORS.dim : sayColor;
  term.write(color);
  if (reveal) {
    for (const ch of text) {
      term.write(ch);
      await sleep(14);
    }
  } else {
    term.write(text);
  }
  term.write(RESET + "\r\n");
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
