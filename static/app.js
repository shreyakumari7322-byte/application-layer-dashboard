// ---------------------------------------------------------------- state

const state = {
  steps: [],
  currentIndex: -1,
  playing: false,
  timer: null,
  mode: "browse",
  lastConnState: null,
};

const STEP_INTERVAL_MS = 750;

// ---------------------------------------------------------------- dom refs

const els = {
  modeBtns: document.querySelectorAll(".mode-btn"),
  forms: document.querySelectorAll(".activity-form"),
  activityStatus: document.getElementById("activityStatus"),
  activityLog: document.getElementById("activityLog"),
  emptyState: document.getElementById("emptyState"),
  timeline: document.getElementById("timeline"),
  scrubber: document.getElementById("scrubber"),
  scrubLabel: document.getElementById("scrubLabel"),
  connectionStatus: document.getElementById("connectionStatus"),
  ctrlPrev: document.getElementById("ctrl-prev"),
  ctrlPlayPause: document.getElementById("ctrl-playpause"),
  ctrlNext: document.getElementById("ctrl-next"),
  ctrlReplay: document.getElementById("ctrl-replay"),
  streamPlay: document.getElementById("stream-play"),
  streamPause: document.getElementById("stream-pause"),
  streamBar: document.getElementById("stream-visual-bar"),
  wirePacket: document.getElementById("wirePacket"),
  wireLine: document.getElementById("wireLine"),
  wireCaption: document.getElementById("wireCaption"),
  wireNodeClient: document.getElementById("nodeClient"),
  wireNodeServer: document.getElementById("nodeServer"),
  connStateBadge: document.getElementById("connStateBadge"),
  osiLayers: document.querySelectorAll(".osi-layer"),
  viewTabs: document.querySelectorAll(".view-tab"),
};

// ---------------------------------------------------------------- view tabs

els.viewTabs.forEach((btn) => {
  btn.addEventListener("click", () => {
    els.viewTabs.forEach((b) => b.classList.toggle("active", b === btn));
    els.timeline.classList.remove("filter-application", "filter-transport");
    const view = btn.dataset.view;
    if (view === "application") els.timeline.classList.add("filter-application");
    if (view === "transport") els.timeline.classList.add("filter-transport");
    // scroll the current step back into view under the new filter
    if (state.currentIndex >= 0) {
      const row = els.timeline.children[state.currentIndex];
      if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
});

// ---------------------------------------------------------------- mode switching

els.modeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    const mode = btn.dataset.mode;
    state.mode = mode;
    els.modeBtns.forEach((b) => b.classList.toggle("active", b === btn));
    els.forms.forEach((f) => f.classList.toggle("hidden", f.dataset.mode !== mode));
  });
});

// ---------------------------------------------------------------- logging / status

function logActivity(text) {
  const li = document.createElement("li");
  li.textContent = text;
  li.classList.add("new");
  els.activityLog.prepend(li);
  setTimeout(() => li.classList.remove("new"), 800);
}

function setStatus(text) { els.activityStatus.textContent = text; }

function setConnectionLive(isLive) {
  els.connectionStatus.classList.toggle("live", isLive);
  els.connectionStatus.innerHTML = isLive
    ? '<span class="dot"></span> exchanging messages'
    : '<span class="dot"></span> idle';
}

// ---------------------------------------------------------------- API calls

async function callApi(path, body) {
  setConnectionLive(true);
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    return await res.json();
  } finally {
    setConnectionLive(false);
  }
}

// ---------------------------------------------------------------- form: browsing

document.getElementById("form-browse").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = document.getElementById("browse-url").value.trim();
  if (!url) return;
  setStatus(`Visiting ${url} …`);
  logActivity(`Browse → ${url}`);
  const data = await callApi("/api/simulate/browse", { url });
  loadSequence(data.steps);
  setStatus(`Loaded ${url}`);
});

// ---------------------------------------------------------------- form: mail

document.getElementById("form-mail").addEventListener("submit", async (e) => {
  e.preventDefault();
  const to = document.getElementById("mail-to").value.trim();
  const subject = document.getElementById("mail-subject").value.trim();
  const body = document.getElementById("mail-body").value.trim();
  if (!to) return;
  setStatus(`Sending mail to ${to} …`);
  logActivity(`Mail → ${to} ("${subject}")`);
  const data = await callApi("/api/simulate/mail", { to, subject, body });
  loadSequence(data.steps);
  setStatus(`Mail queued for ${to}`);
});

// ---------------------------------------------------------------- form: streaming

let streamBarTimer = null;

els.streamPlay.addEventListener("click", async () => {
  const quality = document.getElementById("stream-quality").value;
  setStatus(`Starting stream at ${quality} …`);
  logActivity(`Stream play → ${quality}`);
  els.streamPlay.disabled = true;
  els.streamPause.disabled = false;

  const data = await callApi("/api/simulate/stream", { quality });
  loadSequence(data.steps);
  setStatus(`Streaming at ${quality}`);

  let pct = 0;
  clearInterval(streamBarTimer);
  streamBarTimer = setInterval(() => {
    pct = Math.min(100, pct + 2);
    els.streamBar.style.width = pct + "%";
    if (pct >= 100) clearInterval(streamBarTimer);
  }, 200);
});

els.streamPause.addEventListener("click", () => {
  clearInterval(streamBarTimer);
  els.streamPlay.disabled = false;
  els.streamPause.disabled = true;
  setStatus("Stream paused");
  logActivity("Stream paused");
});

// ---------------------------------------------------------------- timeline rendering

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function loadSequence(steps) {
  state.steps = steps;
  state.currentIndex = -1;
  state.lastConnState = null;
  stopPlaying();

  els.emptyState.style.display = "none";
  els.timeline.classList.add("active");
  els.timeline.innerHTML = "";

  steps.forEach((step) => {
    if (step.type === "divider") {
      const div = document.createElement("div");
      div.className = `layer-divider layer-${step.layer}`;
      div.dataset.index = step.seq;
      div.innerHTML = `<span>${escapeHtml(step.label)}</span>`;
      els.timeline.appendChild(div);
      return;
    }

    const row = document.createElement("div");
    row.className = `step dir-${step.direction} layer-${step.layer}`;
    row.dataset.index = step.seq;

    const arrow = step.direction === "c2s" ? "client → server" : "server → client";

    const fieldsHtml = Object.entries(step.fields || {})
      .map(([k, v]) => `<span class="field-chip"><b>${escapeHtml(k)}:</b> ${escapeHtml(String(v))}</span>`)
      .join("");

    row.innerHTML = `
      <div class="step-time">t+${step.t_ms}ms</div>
      <div class="step-card">
        <div class="step-header">
          <span class="step-proto-badge ${step.protocol}">${step.protocol}</span>
          <span class="step-layer-tag">${step.layer}</span>
          <span class="step-arrow">${arrow}</span>
          <span class="step-label">${escapeHtml(step.label)}</span>
        </div>
        <div class="step-body">
          <pre class="step-raw">${escapeHtml(step.raw)}</pre>
          ${fieldsHtml ? `<div class="step-fields">${fieldsHtml}</div>` : ""}
        </div>
      </div>
    `;
    els.timeline.appendChild(row);
  });

  els.scrubber.max = steps.length - 1;
  els.scrubber.value = -1;
  resetWire();
  updateReveal();
  startPlaying();
}

function resetWire() {
  els.wirePacket.className = "wire-packet";
  els.wirePacket.style.left = "0%";
  els.wireLine.className = "wire-line";
  els.wireCaption.textContent = "Waiting for activity…";
  els.wireNodeClient.classList.remove("active-pulse", "pinging");
  els.wireNodeServer.classList.remove("active-pulse", "pinging");
  els.connStateBadge.textContent = "—";
  els.connStateBadge.className = "conn-state-badge";
  els.osiLayers.forEach((l) => l.classList.remove("osi-active"));
}

function updateReveal() {
  const rows = els.timeline.children;
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const revealed = i <= state.currentIndex;
    row.classList.toggle("revealed", revealed);
    row.classList.toggle("current", i === state.currentIndex);
  }
  const total = state.steps.length;
  const shown = Math.max(0, state.currentIndex + 1);
  els.scrubLabel.textContent = `${shown} / ${total}`;
  els.scrubber.value = state.currentIndex;

  if (state.currentIndex >= 0) {
    const currentRow = els.timeline.children[state.currentIndex];
    if (currentRow) currentRow.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  els.ctrlPrev.disabled = state.currentIndex <= -1;
  els.ctrlNext.disabled = state.currentIndex >= total - 1;

  updateWire();
}

function updateWire() {
  if (state.currentIndex < 0) { resetWire(); return; }

  const step = state.steps[state.currentIndex];
  if (!step || step.type === "divider") return;

  // Move packet along the wire
  const toRight = step.direction === "c2s";
  els.wirePacket.style.left = toRight ? "100%" : "0%";
  els.wirePacket.className = `wire-packet visible proto-${step.protocol}`;
  els.wireCaption.textContent = `${step.protocol} — ${step.label}`;

  els.wireNodeClient.classList.toggle("active-pulse", !toRight);
  els.wireNodeServer.classList.toggle("active-pulse", toRight);
  setTimeout(() => {
    els.wireNodeClient.classList.remove("active-pulse");
    els.wireNodeServer.classList.remove("active-pulse");
  }, 500);

  // OSI rail
  els.osiLayers.forEach((l) => l.classList.toggle("osi-active", l.dataset.layer === step.layer));

  // Connection state
  if (step.conn_state) {
    state.lastConnState = step.conn_state;
  }
  if (state.lastConnState) {
    els.connStateBadge.textContent = state.lastConnState;
    els.connStateBadge.className = "conn-state-badge " + connStateClass(state.lastConnState);
  }
}

function connStateClass(cs) {
  if (cs === "ESTABLISHED") return "state-established";
  if (cs === "CLOSED") return "state-closed";
  if (cs && cs.startsWith("FIN") || cs === "TIME_WAIT") return "state-closing";
  return "";
}

// ---------------------------------------------------------------- playback controls

function startPlaying() {
  if (state.steps.length === 0) return;
  state.playing = true;
  els.ctrlPlayPause.textContent = "⏸";
  clearInterval(state.timer);
  state.timer = setInterval(() => {
    if (state.currentIndex >= state.steps.length - 1) {
      stopPlaying();
      return;
    }
    state.currentIndex += 1;
    updateReveal();
  }, STEP_INTERVAL_MS);
}

function stopPlaying() {
  state.playing = false;
  els.ctrlPlayPause.textContent = "▶";
  clearInterval(state.timer);
}

els.ctrlPlayPause.addEventListener("click", () => {
  if (state.steps.length === 0) return;
  if (state.playing) {
    stopPlaying();
  } else {
    if (state.currentIndex >= state.steps.length - 1) state.currentIndex = -1;
    startPlaying();
  }
});

els.ctrlNext.addEventListener("click", () => {
  stopPlaying();
  if (state.currentIndex < state.steps.length - 1) {
    state.currentIndex += 1;
    updateReveal();
  }
});

els.ctrlPrev.addEventListener("click", () => {
  stopPlaying();
  if (state.currentIndex > -1) {
    state.currentIndex -= 1;
    // recompute lastConnState by scanning backward (state must reflect only revealed steps)
    state.lastConnState = null;
    for (let i = state.currentIndex; i >= 0; i--) {
      const s = state.steps[i];
      if (s && s.conn_state) { state.lastConnState = s.conn_state; break; }
    }
    updateReveal();
  }
});

els.ctrlReplay.addEventListener("click", () => {
  if (state.steps.length === 0) return;
  state.currentIndex = -1;
  state.lastConnState = null;
  updateReveal();
  startPlaying();
});

els.scrubber.addEventListener("input", () => {
  stopPlaying();
  state.currentIndex = parseInt(els.scrubber.value, 10);
  state.lastConnState = null;
  for (let i = state.currentIndex; i >= 0; i--) {
    const s = state.steps[i];
    if (s && s.conn_state) { state.lastConnState = s.conn_state; break; }
  }
  updateReveal();
});
