/**
 * BoardLens Web Studio Client Script
 * Complete integration with live execution, hot assembler, ADC sliders, and digital logic analyzer.
 */

let isRunning = false;
let runInterval = null;
let currentPC = 0;
let ws = null;

// DOM Elements
const oledCanvas = document.getElementById("oledCanvas");
const oledCtx = oledCanvas ? oledCanvas.getContext("2d") : null;
const waveformCanvas = document.getElementById("waveformCanvas");
const waveCtx = waveformCanvas ? waveformCanvas.getContext("2d") : null;

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
const assemblyEditor = document.getElementById("assemblyEditor");
const editorStatus = document.getElementById("editorStatus");

// OLED Dimensions
const OLED_WIDTH = 128;
const OLED_HEIGHT = 64;
const PIXEL_SCALE = 3;

function initCanvas() {
  if (oledCanvas && oledCtx) {
    oledCanvas.width = OLED_WIDTH * PIXEL_SCALE;
    oledCanvas.height = OLED_HEIGHT * PIXEL_SCALE;
    oledCtx.fillStyle = "#030712";
    oledCtx.fillRect(0, 0, oledCanvas.width, oledCanvas.height);
  }

  if (waveformCanvas && waveCtx) {
    waveformCanvas.width = waveformCanvas.parentElement.clientWidth || 600;
    waveformCanvas.height = 160;
    drawWaveforms([]);
  }
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

function drawWaveforms(samples) {
  if (!waveformCanvas || !waveCtx) return;
  const w = waveformCanvas.width;
  const h = waveformCanvas.height;

  // Background
  waveCtx.fillStyle = "#030712";
  waveCtx.fillRect(0, 0, w, h);

  const signals = [
    { name: "CLK", type: "digital", color: "#38bdf8" },
    { name: "PC", type: "bus", color: "#c084fc" },
    { name: "ADDR", type: "bus", color: "#facc15" },
    { name: "WE", type: "digital", color: "#f43f5e" },
    { name: "PA5", type: "digital", color: "#10b981" },
    { name: "TX", type: "digital", color: "#f97316" },
  ];

  const gutterW = 55;
  const plotW = w - gutterW - 10;
  const rowH = Math.floor(h / signals.length);

  waveCtx.font = "10px ui-monospace, monospace";

  signals.forEach((sig, idx) => {
    const yTop = idx * rowH;
    const yMid = yTop + rowH / 2;
    const yBot = yTop + rowH - 4;

    // Row grid divider
    waveCtx.strokeStyle = "#1e293b";
    waveCtx.lineWidth = 1;
    waveCtx.beginPath();
    waveCtx.moveTo(0, yTop + rowH);
    waveCtx.lineTo(w, yTop + rowH);
    waveCtx.stroke();

    // Signal label
    waveCtx.fillStyle = sig.color;
    waveCtx.fillText(sig.name, 6, yMid + 4);

    if (!samples || samples.length === 0) return;

    const count = samples.length;
    const stepW = Math.max(12, plotW / Math.max(16, count));
    const startX = gutterW;

    if (sig.type === "digital") {
      waveCtx.strokeStyle = sig.color;
      waveCtx.lineWidth = 1.5;
      waveCtx.beginPath();

      let lastState = null;
      for (let i = 0; i < count; i++) {
        const s = samples[i];
        let val = 0;
        if (sig.name === "CLK") val = i % 2 === 0 ? 1 : 0;
        else if (sig.name === "WE") val = s.we;
        else if (sig.name === "PA5") val = s.pa5;
        else if (sig.name === "TX") val = s.tx;

        const x0 = startX + i * stepW;
        const x1 = x0 + stepW;
        const yVal = val ? yTop + 4 : yBot;

        if (i === 0) {
          waveCtx.moveTo(x0, yVal);
        } else if (lastState !== val) {
          waveCtx.lineTo(x0, yVal);
        }
        waveCtx.lineTo(x1, yVal);
        lastState = val;
      }
      waveCtx.stroke();
    } else if (sig.type === "bus") {
      waveCtx.strokeStyle = sig.color;
      waveCtx.lineWidth = 1;

      for (let i = 0; i < count; i++) {
        const s = samples[i];
        const x0 = startX + i * stepW;
        const x1 = x0 + stepW;
        const yLow = yBot;
        const yHigh = yTop + 3;

        waveCtx.beginPath();
        waveCtx.moveTo(x0, (yHigh + yLow) / 2);
        waveCtx.lineTo(x0 + 3, yHigh);
        waveCtx.lineTo(x1 - 3, yHigh);
        waveCtx.lineTo(x1, (yHigh + yLow) / 2);
        waveCtx.lineTo(x1 - 3, yLow);
        waveCtx.lineTo(x0 + 3, yLow);
        waveCtx.closePath();
        waveCtx.fillStyle = "rgba(192, 132, 252, 0.08)";
        waveCtx.fill();
        waveCtx.stroke();

        if (stepW >= 24) {
          const rawLabel = sig.name === "PC" ? s.pc : s.addr;
          const label = String(rawLabel).slice(-4);
          waveCtx.fillStyle = sig.color;
          waveCtx.fillText(label, x0 + 4, (yHigh + yLow) / 2 + 3);
        }
      }
    }
  });
}

function switchLeftTab(tab) {
  const disasmBtn = document.getElementById("tabBtnDisasm");
  const editorBtn = document.getElementById("tabBtnEditor");
  const disasmPanel = document.getElementById("disassemblyPanel");
  const editorPanel = document.getElementById("editorPanel");
  const tabMeta = document.getElementById("tabMeta");

  if (tab === "editor") {
    disasmBtn.classList.remove("active");
    editorBtn.classList.add("active");
    disasmPanel.style.display = "none";
    editorPanel.style.display = "flex";
    if (tabMeta) tabMeta.innerText = "Live Hot-Assembler";

    if (assemblyEditor && !assemblyEditor.value) {
      loadCurrentExampleIntoEditor();
    }
  } else {
    disasmBtn.classList.add("active");
    editorBtn.classList.remove("active");
    disasmPanel.style.display = "block";
    editorPanel.style.display = "none";
    if (tabMeta) tabMeta.innerText = "Flash ROM (0x00000000)";
  }
}

async function loadCurrentExampleIntoEditor() {
  if (!exampleSelect || !assemblyEditor) return;
  const ex = exampleSelect.value || "blinky";
  try {
    const res = await fetch("/api/examples");
    const examples = await res.json();
    if (examples[ex]) {
      assemblyEditor.value = examples[ex];
    }
  } catch (err) {
    console.error("Failed to load example into editor:", err);
  }
}

async function flashEditor() {
  if (!assemblyEditor || !editorStatus) return;
  editorStatus.innerText = "Assembling...";
  editorStatus.style.color = "var(--accent-amber)";

  try {
    const res = await fetch("/api/editor/flash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: assemblyEditor.value }),
    });
    const data = await res.json();
    if (res.ok) {
      editorStatus.innerText = `Flashed (${data.bytes_flashed} bytes)`;
      editorStatus.style.color = "var(--accent-emerald)";
      doReset();
    } else {
      editorStatus.innerText = `Error: ${data.detail || "Assembly failed"}`;
      editorStatus.style.color = "var(--accent-rose)";
    }
  } catch (err) {
    editorStatus.innerText = `Error: ${err.message}`;
    editorStatus.style.color = "var(--accent-rose)";
  }
}

async function onAdcChange(channel, millivolts) {
  const mv = parseInt(millivolts, 10);
  const v = (mv / 1000).toFixed(2);
  const rawVal = Math.round((mv / 3300.0) * 4095);
  const valEl = document.getElementById(`adcVal${channel}`);
  if (valEl) {
    valEl.innerText = `${v} V (${rawVal})`;
  }

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: "adc", channel: channel, millivolts: mv }));
  } else {
    await fetch("/api/adc/channel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: channel, millivolts: mv }),
    });
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
    const res = await fetch("/api/memory?address=536870912&length=128");
    const data = await res.json();
    renderMemory(data.rows);
  } catch (err) {
    console.error("Memory fetch failed:", err);
  }
}

async function fetchWaveform() {
  try {
    const res = await fetch("/api/waveform");
    const data = await res.json();
    if (data.samples) {
      drawWaveforms(data.samples);
    }
  } catch (err) {
    console.error("Waveform fetch failed:", err);
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

  // ADC Channels
  if (status.adc && status.adc.channels) {
    status.adc.channels.forEach((ch) => {
      const valEl = document.getElementById(`adcVal${ch.channel}`);
      const sliderEl = document.getElementById(`adcSlider${ch.channel}`);
      if (valEl) {
        valEl.innerText = `${ch.voltage.toFixed(2)} V (${Math.round((ch.millivolts / 3300.0) * 4095)})`;
      }
      if (sliderEl && document.activeElement !== sliderEl) {
        sliderEl.value = ch.millivolts;
      }
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
  fetchWaveform();
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
    fetchWaveform();

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
  fetchWaveform();
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
  loadCurrentExampleIntoEditor();
  doReset();
}

function initWebSocket() {
  try {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.status) updateUI(data.status);
      if (data.oled_pixels) renderOled(data.oled_pixels);
      if (data.uart_tx && terminalLog) {
        terminalLog.innerText += data.uart_tx;
        terminalLog.scrollTop = terminalLog.scrollHeight;
      }
      if (data.waveform) {
        drawWaveforms(data.waveform);
      }
    };

    ws.onerror = (err) => {
      console.warn("WebSocket fallback to HTTP polling:", err);
    };
  } catch (err) {
    console.warn("WebSocket init failed:", err);
  }
}

// Global initialization
window.addEventListener("DOMContentLoaded", () => {
  initCanvas();
  fetchStatus();
  fetchDisassembly();
  fetchMemory();
  updateOled();
  fetchWaveform();
  loadCurrentExampleIntoEditor();
  initWebSocket();

  setInterval(() => {
    if (!isRunning && (!ws || ws.readyState !== WebSocket.OPEN)) {
      updateUart();
      updateOled();
      fetchWaveform();
    }
  }, 500);
});
