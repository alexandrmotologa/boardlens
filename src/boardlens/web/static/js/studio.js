/**
 * BoardLens Web Studio Client Script
 */

let isRunning = false;
let runInterval = null;
let currentPC = 0;
let ws = null;

// DOM Elements
const oledCanvas = document.getElementById("oledCanvas");
const oledCtx = oledCanvas ? oledCanvas.getContext("2d") : null;
const statusBadge = document.getElementById("statusBadge");
const cycleCounter = document.getElementById("cycleCounter");
const pcDisplay = document.getElementById("pcDisplay");
const disassemblyList = document.getElementById("disassemblyList");
const registersGrid = document.getElementById("registersGrid");
const gpioPinsContainer = document.getElementById("gpioPinsContainer");
const terminalLog = document.getElementById("terminalLog");
const uartInput = document.getElementById("uartInput");
const sramHexTable = document.getElementById("sramHexTable");
const exampleSelect = document.getElementById("exampleSelect");

// OLED Dimensions
const OLED_WIDTH = 128;
const OLED_HEIGHT = 64;
const PIXEL_SCALE = 3;

function initCanvas() {
  if (!oledCanvas || !oledCtx) return;
  oledCanvas.width = OLED_WIDTH * PIXEL_SCALE;
  oledCanvas.height = OLED_HEIGHT * PIXEL_SCALE;
  oledCtx.fillStyle = "#030712";
  oledCtx.fillRect(0, 0, oledCanvas.width, oledCanvas.height);
}

function renderOled(pixels) {
  if (!oledCtx || !pixels || !pixels.length) return;
  oledCtx.fillStyle = "#030712";
  oledCtx.fillRect(0, 0, oledCanvas.width, oledCanvas.height);

  oledCtx.fillStyle = "#38bdf8";
  for (let y = 0; y < OLED_HEIGHT; y++) {
    const row = pixels[y];
    if (!row) continue;
    for (let x = 0; x < OLED_WIDTH; x++) {
      if (row[x] === 1) {
        oledCtx.fillRect(
          x * PIXEL_SCALE,
          y * PIXEL_SCALE,
          PIXEL_SCALE - 0.5,
          PIXEL_SCALE - 0.5
        );
      }
    }
  }
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateUI(data);
  } catch (err) {
    console.error("Status fetch failed:", err);
  }
}

async function fetchDisassembly() {
  try {
    const res = await fetch("/api/disassembly");
    const items = await res.json();
    renderDisassembly(items);
  } catch (err) {
    console.error("Disassembly fetch failed:", err);
  }
}

async function fetchMemory() {
  try {
    const res = await fetch("/api/memory?address=536870912&length=128"); // 0x20000000
    const data = await res.json();
    renderMemory(data.rows);
  } catch (err) {
    console.error("Memory fetch failed:", err);
  }
}

function renderDisassembly(items) {
  if (!disassemblyList) return;
  disassemblyList.innerHTML = "";
  items.forEach((item) => {
    const line = document.createElement("div");
    line.className = `code-line ${item.is_current ? "current" : ""}`;
    line.innerHTML = `
      <span class="code-addr">${item.address}</span>
      <span class="code-raw">${item.raw}</span>
      <span class="code-text">${item.mnemonic}</span>
    `;
    disassemblyList.appendChild(line);
  });
}

function renderMemory(rows) {
  if (!sramHexTable || !rows) return;
  sramHexTable.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="hex-addr">${row.address}</td>
      <td class="hex-bytes">${row.hex}</td>
      <td class="hex-ascii">${row.ascii}</td>
    `;
    sramHexTable.appendChild(tr);
  });
}

function updateUI(status) {
  if (!status) return;

  // Header stats
  if (cycleCounter) cycleCounter.innerText = `${status.cycles.toLocaleString()} cycles`;
  if (pcDisplay) pcDisplay.innerText = status.pc;
  if (statusBadge) {
    if (status.halted) {
      statusBadge.innerText = "HALTED";
      statusBadge.style.color = "var(--accent-rose)";
      statusBadge.style.borderColor = "rgba(244,63,94,0.3)";
    } else {
      statusBadge.innerText = isRunning ? "RUNNING" : "READY";
      statusBadge.style.color = "var(--accent-emerald)";
      statusBadge.style.borderColor = "rgba(16,185,129,0.3)";
    }
  }

  // Registers
  if (registersGrid && status.registers && status.registers.gpr) {
    registersGrid.innerHTML = "";
    const gpr = status.registers.gpr;
    Object.keys(gpr).forEach((key) => {
      const r = gpr[key];
      const div = document.createElement("div");
      div.className = "reg-row";
      div.innerHTML = `
        <span class="reg-name">${key} (${r.abi})</span>
        <span class="reg-val">${r.hex}</span>
      `;
      registersGrid.appendChild(div);
    });
  }

  // GPIO Pins
  if (gpioPinsContainer && status.gpio && status.gpio.pins) {
    gpioPinsContainer.innerHTML = "";
    status.gpio.pins.forEach((p) => {
      const slot = document.createElement("div");
      slot.className = "pin-slot";
      const isHigh = p.state;
      slot.innerHTML = `
        <span class="pin-label">PA${p.pin}</span>
        <div class="pin-led ${isHigh ? "active" : ""}"></div>
        <button class="pin-toggle" onclick="togglePin(${p.pin}, ${!isHigh})">${isHigh ? "1" : "0"}</button>
      `;
      gpioPinsContainer.appendChild(slot);
    });
  }
}

async function togglePin(pin, state) {
  await fetch("/api/gpio/input", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: pin, high: state }),
  });
  fetchStatus();
}

async function doStep() {
  const res = await fetch("/api/step", { method: "POST" });
  const data = await res.json();
  updateUI(data.status);
  fetchDisassembly();
  fetchMemory();
  updateUart();
  updateOled();
}

async function doRun() {
  if (isRunning) return;
  isRunning = true;
  if (statusBadge) statusBadge.innerText = "RUNNING";

  runInterval = setInterval(async () => {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cycles: 500 }),
    });
    const data = await res.json();
    updateUI(data.status);
    updateUart();
    updateOled();

    if (data.status.halted) {
      doPause();
      fetchDisassembly();
      fetchMemory();
    }
  }, 100);
}

function doPause() {
  isRunning = false;
  if (runInterval) {
    clearInterval(runInterval);
    runInterval = null;
  }
  if (statusBadge) statusBadge.innerText = "PAUSED";
}

async function doReset() {
  doPause();
  await fetch("/api/reset", { method: "POST" });
  if (terminalLog) terminalLog.innerText = "";
  fetchStatus();
  fetchDisassembly();
  fetchMemory();
  updateOled();
}

async function updateUart() {
  const res = await fetch("/api/uart/read");
  const data = await res.json();
  if (data.output && terminalLog) {
    terminalLog.innerText += data.output;
    terminalLog.scrollTop = terminalLog.scrollHeight;
  }
}

async function updateOled() {
  const res = await fetch("/api/oled/pixels");
  const pixels = await res.json();
  renderOled(pixels);
}

async function sendUart() {
  if (!uartInput || !uartInput.value) return;
  const text = uartInput.value;
  uartInput.value = "";
  await fetch("/api/uart/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: text }),
  });
}

async function loadExample() {
  if (!exampleSelect) return;
  const ex = exampleSelect.value;
  await fetch("/api/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ example: ex }),
  });
  doReset();
}

// Global initialization
window.addEventListener("DOMContentLoaded", () => {
  initCanvas();
  fetchStatus();
  fetchDisassembly();
  fetchMemory();
  updateOled();

  // Polling for UART & OLED updates if not using WebSockets
  setInterval(() => {
    if (!isRunning) {
      updateUart();
      updateOled();
    }
  }, 500);
});
