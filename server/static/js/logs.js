// static/js/logs.js

// ---------- NOTIFY HELPERS ----------

function notifyLogs(message, type = "info") {
  if (typeof showAlert === "function") return showAlert(message, type);
  if (typeof showToast === "function") return showToast(message, type === "danger" ? "error" : type);
  try {
    alert(message);
  } catch (_) {
    console.log(`[${type}] ${message}`);
  }
}

// ---------- HELPERS ----------

function safeText(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch (_) {
    return String(v);
  }
}

function truncate(s, n = 180) {
  const str = safeText(s);
  if (str.length <= n) return str;
  return str.slice(0, n) + "…";
}

function normalizeMethod(m) {
  const s = safeText(m);
  return s === "—" ? "—" : s.toUpperCase();
}

// ---------- API ----------

async function apiGetAllLogs() {
  const url = global_sudo ? window.get_all_logs_SUDO : window.get_user_logs_API;
  const res = await fetch(url);
  let data = await res.json();
  // Expecting: { result:"success", message:[...] } (matching your images.js convention)
  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }

  return data.message || [];
}

// ---------- RENDERING ----------

function renderLogs(rows) {
  const tbody = document.getElementById("logs-tbody");
  const wrapper = document.getElementById("logs-table-wrapper");
  const empty = document.getElementById("logs-empty");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!rows || rows.length === 0) {
    wrapper?.classList.add("hidden");
    empty?.classList.remove("hidden");
    return;
  }
  wrapper?.classList.remove("hidden");
  empty?.classList.add("hidden");
  rows.forEach((log) => {
    const tr = document.createElement("tr");

    const idTd = document.createElement("td");
    idTd.textContent = safeText(log.id);

    const userTd = document.createElement("td");
    userTd.textContent = safeText(log.user);

    const methodTd = document.createElement("td");
    methodTd.textContent = normalizeMethod(log.method);

    const pathTd = document.createElement("td");
    pathTd.textContent = safeText(log.path);

    const codeTd = document.createElement("td");
    codeTd.textContent = safeText(log.response_code);

    const respTd = document.createElement("td");
    respTd.title = safeText(log.response); // full on hover
    respTd.textContent = truncate(log.response, 220);

    tr.appendChild(idTd);
    tr.appendChild(userTd);
    tr.appendChild(methodTd);
    tr.appendChild(pathTd);
    tr.appendChild(codeTd);
    tr.appendChild(respTd);
    tr.classList.add("clickable-row");
    tr.title = "Click to view details";
    tr.addEventListener("click", () => openLogModal(log));

    tbody.appendChild(tr);
  });
}

// ---------- FLOW ----------

let _allLogs = [];

function filterLogs(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return _allLogs;

  return _allLogs.filter((log) => {
    const hay = [
      log.id,
      log.user,
      log.method,
      log.path,
      log.response_code,
      log.response,
    ]
      .map((x) => safeText(x).toLowerCase())
      .join(" | ");

    return hay.includes(q);
  });
}

async function refreshLogs() {
  try {
    const logs = await apiGetAllLogs();
    _allLogs = Array.isArray(logs) ? logs : [];
    renderLogs(_allLogs);
  } catch (err) {
    console.error("Failed to load logs:", err);
    notifyLogs(`❌ Failed to load logs: ${err.message}`, "danger");
    _allLogs = [];
    renderLogs([]);
  }
}

// ---------- UI WIRING ----------

function setupLogsUI() {
  const refreshBtn = document.getElementById("refresh-logs-btn");
  refreshBtn?.addEventListener("click", refreshLogs);

  const search = document.getElementById("logs-search");
  search?.addEventListener("input", (e) => {
    const filtered = filterLogs(e.target.value);
    renderLogs(filtered);
  });
}
// ---------- MODAL HELPERS ----------

function isProbablyJSON(text) {
  if (text == null) return false;
  const s = String(text).trim();
  return (s.startsWith("{") && s.endsWith("}")) || (s.startsWith("[") && s.endsWith("]"));
}

function prettyResponseText(resp) {
  if (resp == null) return "—";
  const s = typeof resp === "string" ? resp : JSON.stringify(resp);
  const trimmed = s.trim();

  if (isProbablyJSON(trimmed)) {
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch (_) {
      // fall through
    }
  }
  return s;
}

async function apiPurgeLogs() {
  const url = global_sudo
    ? window.purge_all_logs_SUDO
    : window.purge_all_logs_API;

  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  let data = await res.json();
  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }
}

function setupPurgeLogsButton() {
  const btn = document.getElementById("purge-logs-btn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const ok = confirm(
      "This will permanently delete all logs.\n\nAre you sure?"
    );
    if (!ok) return;

    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Purging...";

    try {
      await apiPurgeLogs();
      showAlert("Logs purged successfully.", "success");
      await refreshLogs?.(); // if you have it
    } catch (err) {
      console.error(err);
      showAlert(`Failed to purge logs: ${err.message}`, "danger");
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  });
}


function openLogModal(log) {
  const modal = document.getElementById("log-modal");
  if (!modal) return;

  document.getElementById("log-modal-id").textContent = log.id ?? "—";
  document.getElementById("log-modal-user").textContent = log.user ?? "—";
  document.getElementById("log-modal-method").textContent = log.method ?? "—";
  document.getElementById("log-modal-path").textContent = log.path ?? "—";
  document.getElementById("log-modal-code").textContent = log.response_code ?? "—";

  const responseText = prettyResponseText(log.response);
  document.getElementById("log-modal-response").textContent = responseText;

  // Title: METHOD + PATH (nice quick scan)
  const title = `${log.method ?? "—"} ${log.path ?? ""}`.trim();
  document.getElementById("log-modal-title").textContent = title || "Log entry";

  modal.classList.remove("hidden");
  modal.hidden = false;
  document.body.style.overflow = "hidden"; // prevent background scroll
}

function closeLogModal() {
  const modal = document.getElementById("log-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  document.body.style.overflow = "";
}

function setupLogModal() {
  const modal = document.getElementById("log-modal");
  if (!modal) return;

  // Close buttons
  document.getElementById("log-modal-close")?.addEventListener("click", closeLogModal);
  document.getElementById("log-modal-ok")?.addEventListener("click", closeLogModal);

  // Click outside
  modal.querySelector("[data-close='true']")?.addEventListener("click", closeLogModal);

  // Esc
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) closeLogModal();
  });

  // Copy response
  document.getElementById("log-modal-copy")?.addEventListener("click", async () => {
    const text = document.getElementById("log-modal-response")?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(text);
      if (typeof showToast === "function") showToast("Copied ✅", "success");
    } catch (err) {
      console.error("Copy failed:", err);
      if (typeof showToast === "function") showToast("Copy failed ❌", "error");
    }
  });
}

// Call this in DOMContentLoaded in logs.js
document.addEventListener("DOMContentLoaded", () => {
  setupLogModal();
  setupPurgeLogsButton();
});

// ---------- INIT ----------

document.addEventListener("DOMContentLoaded", async () => {
  setupLogsUI();
  await refreshLogs(); // if you prefer only on tab-open, tell me what your tab switcher looks like and I’ll hook it there
});
document.addEventListener("DOMContentLoaded", () => {
  const openBtn = document.getElementById("open-logs");
  const modal = document.getElementById("user-logs-modal");
  const refreshBtn = document.getElementById("refresh-user-logs-btn");

  async function openUserLogs() {
    if (!modal) return;
    modal.classList.remove("hidden");
    modal.removeAttribute("hidden");

    // expects security.js to define refreshLogs() that renders into:
    // #user-logs-tbody, #user-logs-empty, etc.
    if (typeof refreshLogs === "function") {
      try {
        await refreshLogs();
      } catch (e) {
        console.error(e);
      }
    } else {
      console.warn("refreshLogs() not found. Define it in security.js");
    }
  }

  openBtn?.addEventListener("click", openUserLogs);
  refreshBtn?.addEventListener("click", async () => {
    if (typeof refreshLogs === "function") await refreshLogs();
  });

  // Optional: search filter hook (if your refreshLogs supports it)
  // document.getElementById("user-logs-search")?.addEventListener("input", () => refreshLogs?.());
});
