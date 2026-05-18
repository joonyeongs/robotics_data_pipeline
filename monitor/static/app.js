const state = {
  samples: [],
  stats: {},
  selectedId: null,
  refreshTimer: null,
};

const els = {
  statusLine: document.getElementById("statusLine"),
  topicFilter: document.getElementById("topicFilter"),
  searchInput: document.getElementById("searchInput"),
  autoRefresh: document.getElementById("autoRefresh"),
  refreshButton: document.getElementById("refreshButton"),
  totalMetric: document.getElementById("totalMetric"),
  successMetric: document.getElementById("successMetric"),
  failureMetric: document.getElementById("failureMetric"),
  rateMetric: document.getElementById("rateMetric"),
  sampleCount: document.getElementById("sampleCount"),
  samplesBody: document.getElementById("samplesBody"),
  selectedTitle: document.getElementById("selectedTitle"),
  selectedStatus: document.getElementById("selectedStatus"),
  videoPlayer: document.getElementById("videoPlayer"),
  videoEmpty: document.getElementById("videoEmpty"),
  sampleDetails: document.getElementById("sampleDetails"),
  taskStats: document.getElementById("taskStats"),
  metadataState: document.getElementById("metadataState"),
  metadataView: document.getElementById("metadataView"),
};

function text(value) {
  if (value === true) return "true";
  if (value === false) return "false";
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function timeText(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function durationText(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "-";
  return `${numeric.toFixed(2)}s`;
}

function statusBadge(classification) {
  const span = document.createElement("span");
  span.className = `badge ${classification === "success" || classification === "failure" ? classification : "neutral"}`;
  span.textContent = text(classification);
  return span;
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function filteredSamples() {
  const query = els.searchInput.value.trim().toLowerCase();
  if (!query) return state.samples;
  return state.samples.filter((sample) => {
    return [
      sample.sample_id,
      sample.task_name,
      sample.dataset_file,
      sample.demo_key,
      sample.classification,
      sample.topic,
    ]
      .map((item) => text(item).toLowerCase())
      .some((item) => item.includes(query));
  });
}

function renderStats() {
  const total = Number(state.stats.total || 0);
  const success = Number(state.stats.success || 0);
  const failure = Number(state.stats.failure || 0);
  const rate = Number(state.stats.success_rate || 0);

  els.totalMetric.textContent = total.toLocaleString();
  els.successMetric.textContent = success.toLocaleString();
  els.failureMetric.textContent = failure.toLocaleString();
  els.rateMetric.textContent = `${Math.round(rate * 100)}%`;

  els.taskStats.replaceChildren();
  const byTask = state.stats.by_task || {};
  const rows = Object.entries(byTask).sort((a, b) => b[1].total - a[1].total);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No task data";
    els.taskStats.appendChild(empty);
    return;
  }

  for (const [task, counts] of rows.slice(0, 12)) {
    const row = document.createElement("div");
    row.className = "task-row";

    const name = document.createElement("span");
    name.className = "task-name";
    name.textContent = task;

    const stats = document.createElement("span");
    stats.className = "task-counts";
    stats.textContent = `${counts.total} total / ${counts.success} ok / ${counts.failure} fail`;

    row.append(name, stats);
    els.taskStats.appendChild(row);
  }
}

function renderSamples() {
  const samples = filteredSamples();
  els.sampleCount.textContent = `${samples.length} rows`;
  els.samplesBody.replaceChildren();

  for (const sample of samples) {
    const row = document.createElement("tr");
    if (sample.sample_id === state.selectedId) row.classList.add("selected");
    row.addEventListener("click", () => selectSample(sample.sample_id));

    const statusCell = document.createElement("td");
    statusCell.appendChild(statusBadge(sample.classification));

    const task = document.createElement("td");
    task.textContent = text(sample.task_name);
    task.title = text(sample.sample_id);

    const demo = document.createElement("td");
    demo.textContent = text(sample.demo_key);

    const actions = document.createElement("td");
    actions.textContent = text(sample.use_actions);

    const consumed = document.createElement("td");
    consumed.textContent = timeText(sample.consumed_at);
    consumed.title = text(sample.consumed_at);

    row.append(statusCell, task, demo, actions, consumed);
    els.samplesBody.appendChild(row);
  }
}

function renderDetails(sample) {
  els.sampleDetails.replaceChildren();
  const rows = [
    ["Sample ID", sample.sample_id],
    ["Topic", sample.topic],
    ["Dataset", sample.dataset_file],
    ["Demo", sample.demo_key],
    ["Use Actions", sample.use_actions],
    ["Playback OK", sample.playback_ok],
    ["Duration", durationText(sample.duration_seconds)],
    ["Produced", sample.produced_at],
    ["Consumed", sample.consumed_at],
  ];

  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = text(value);
    els.sampleDetails.append(dt, dd);
  }
}

async function renderMetadata(sample) {
  els.metadataState.textContent = "Loading";
  els.metadataView.textContent = "{}";
  if (!sample.metadata_url) {
    els.metadataState.textContent = "Unavailable";
    return;
  }
  try {
    const metadata = await fetchJson(sample.metadata_url);
    els.metadataState.textContent = "Loaded";
    els.metadataView.textContent = JSON.stringify(metadata, null, 2);
  } catch (error) {
    els.metadataState.textContent = "Unavailable";
    els.metadataView.textContent = JSON.stringify({ error: error.message }, null, 2);
  }
}

function clearSelection() {
  els.selectedTitle.textContent = "Replay";
  els.selectedStatus.className = "badge neutral";
  els.selectedStatus.textContent = "No sample";
  els.videoPlayer.removeAttribute("src");
  els.videoPlayer.load();
  els.videoPlayer.style.display = "none";
  els.videoEmpty.style.display = "grid";
  els.sampleDetails.replaceChildren();
  els.metadataState.textContent = "No sample";
  els.metadataView.textContent = "{}";
}

function selectSample(sampleId) {
  const sample = state.samples.find((item) => item.sample_id === sampleId);
  const isSameSelection = sample && state.selectedId === sample.sample_id;
  state.selectedId = sample ? sample.sample_id : null;
  renderSamples();

  if (!sample) {
    clearSelection();
    return;
  }

  els.selectedTitle.textContent = text(sample.task_name);
  els.selectedStatus.replaceChildren();
  els.selectedStatus.className = `badge ${sample.classification}`;
  els.selectedStatus.textContent = text(sample.classification);

  if (sample.video_url) {
    if (els.videoPlayer.getAttribute("src") !== sample.video_url) {
      els.videoPlayer.src = sample.video_url;
    }
    els.videoPlayer.style.display = "block";
    els.videoEmpty.style.display = "none";
  } else {
    els.videoPlayer.removeAttribute("src");
    els.videoPlayer.load();
    els.videoPlayer.style.display = "none";
    els.videoEmpty.style.display = "grid";
  }

  renderDetails(sample);
  if (!isSameSelection) {
    renderMetadata(sample);
  }
}

function selectDefaultIfNeeded() {
  if (state.selectedId && state.samples.some((sample) => sample.sample_id === state.selectedId)) {
    selectSample(state.selectedId);
    return;
  }
  if (state.samples.length) {
    selectSample(state.samples[0].sample_id);
    return;
  }
  clearSelection();
}

async function refresh() {
  const classification = els.topicFilter.value;
  try {
    const [samples, stats] = await Promise.all([
      fetchJson(`/api/samples?classification=${encodeURIComponent(classification)}&limit=500`),
      fetchJson("/api/stats"),
    ]);
    state.samples = samples;
    state.stats = stats;
    els.statusLine.textContent = `Last refresh ${new Date().toLocaleTimeString()}`;
    renderStats();
    renderSamples();
    selectDefaultIfNeeded();
  } catch (error) {
    els.statusLine.textContent = `Monitor error: ${error.message}`;
  }
}

function configureAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
  if (els.autoRefresh.checked) {
    state.refreshTimer = setInterval(refresh, 2000);
  }
}

els.refreshButton.addEventListener("click", refresh);
els.topicFilter.addEventListener("change", refresh);
els.searchInput.addEventListener("input", () => {
  renderSamples();
  selectDefaultIfNeeded();
});
els.autoRefresh.addEventListener("change", configureAutoRefresh);

configureAutoRefresh();
refresh();
