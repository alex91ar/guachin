// static/js/configuration.js

async function fetchConfig() {
  
    const url = getConfigGetUrl();
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.result !== "success") throw new Error(data.message || "Failed to load config");
    return data.message || {};
  }

  function toast(msg, type = "info") {
    if (typeof window.showToast === "function") return window.showToast(msg, type);
    alert(msg);
  }

  function getConfigGetUrl() {
    // prefer SUDO if global_sudo is active, else normal
    if (window.global_sudo && window.get_config_SUDO) return window.get_config_SUDO;
    return window.get_config_API || window.get_config_SUDO || "/config";
  }

  function getConfigPatchUrl() {
    if (window.global_sudo && window.patch_config_SUDO) return window.patch_config_SUDO;
    return window.patch_config_API || window.patch_config_SUDO || "/config";
  }

function getDeletePatchUrl() {
    if (window.global_sudo && window.delete_config_SUDO) return window.delete_config_SUDO;
    return window.delete_config_API || window.delete_config_SUDO || "/config";
  }

  function safeStringify(v) {
    try {
      if (typeof v === "string") return JSON.stringify(v);
      return JSON.stringify(v);
    } catch {
      return JSON.stringify(String(v));
    }
  }

  function matchFilter(key, value, q) {
    if (!q) return true;
    const hay = (key + " " + safeStringify(value)).toLowerCase();
    return hay.includes(q.toLowerCase());
  }

  async function deleteConfig(k, persist) {
    
    const url = getDeletePatchUrl();
    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ k, persist}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.result !== "success") throw new Error(data.message || "Failed to update config");
    return data.message;
  }

  async function patchConfig(k, v, persist, type ) {
    
    const url = getConfigPatchUrl();
    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ k, v, persist: !!persist, type }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.result !== "success") throw new Error(data.message || "Failed to update config");
    return data.message;
  }

 function renderConfigTable(items) {
  const tbody = document.getElementById("config-tbody");
  const wrapper = document.getElementById("config-table-wrapper");
  const empty = document.getElementById("config-empty");
  const search = document.getElementById("config-search");
  if (!tbody || !wrapper || !empty) return;

  const q = (search?.value || "").trim().toLowerCase();

  // items: [{ k:"KEY", v:any, type:"str|int|float|bool|dict|list|NoneType|..." }]
  const rows = (Array.isArray(items) ? items : [])
    .filter((it) => {
      const key = String(it?.k ?? "");
      const val = safeStringify(it?.v);
      if (!q) return true;
      return (key + " " + val + " " + String(it?.type ?? "")).toLowerCase().includes(q);
    })
    .sort((a, b) => String(a.k || "").localeCompare(String(b.k || "")));

  tbody.innerHTML = "";

  if (!rows.length) {
    wrapper.classList.add("hidden");
    empty.classList.remove("hidden");
    return;
  }
  wrapper.classList.remove("hidden");
  empty.classList.add("hidden");

  rows.forEach((item) => {
    const key = String(item?.k ?? "");
    const currentValue = item?.v;
    const type = String(item?.type ?? "").toLowerCase();

    const tr = document.createElement("tr");

    // --- Key ---
    const tdKey = document.createElement("td");
    tdKey.textContent = key;

    // --- Value (editable, based on type) ---
    const tdVal = document.createElement("td");

    let valueEl; // input/textarea/select

    // pick editor by type
    if (type === "bool" || type === "boolean") {
      const sel = document.createElement("select");
      sel.className = "input small";
      const optTrue = document.createElement("option");
      optTrue.value = "true";
      optTrue.textContent = "true";
      const optFalse = document.createElement("option");
      optFalse.value = "false";
      optFalse.textContent = "false";
      sel.appendChild(optTrue);
      sel.appendChild(optFalse);
      sel.value = String(!!currentValue);
      valueEl = sel;
    } else if (type === "int" || type === "integer" || type === "float" || type === "number") {
      const inp = document.createElement("input");
      inp.className = "input small";
      inp.type = "number";
      inp.step = (type === "float") ? "any" : "1";
      inp.value = (currentValue ?? "").toString();
      valueEl = inp;
    } else if (type === "dict" || type === "list" || type === "object" || type === "array") {
      const ta = document.createElement("textarea");
      ta.className = "input small";
      ta.rows = 3;
      ta.style.width = "100%";
      ta.style.resize = "vertical";
      ta.style.fontFamily =
        "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace";
      ta.value = safeStringify(currentValue);
      valueEl = ta;
    } else {
      // default: string-ish
      const inp = document.createElement("input");
      inp.className = "input small";
      inp.type = "text";
      inp.style.width = "100%";
      inp.value = (currentValue ?? "").toString();
      valueEl = inp;
    }

    tdVal.appendChild(valueEl);

    // --- Persist ---
    const tdPersist = document.createElement("td");
    const chkWrap = document.createElement("label");
    chkWrap.style.display = "flex";
    chkWrap.style.alignItems = "center";
    chkWrap.style.gap = ".5rem";

    const chk = document.createElement("input");
    chk.type = "checkbox";

    const lbl = document.createElement("span");
    lbl.className = "meta";
    lbl.textContent = "Persist";

    chkWrap.appendChild(chk);
    chkWrap.appendChild(lbl);
    tdPersist.appendChild(chkWrap);

    // --- Actions (Save + Delete) ---
    const tdAction = document.createElement("td");
    tdAction.className = "right";

    const saveBtn = document.createElement("button");
    saveBtn.className = "btn primary btn-sm";
    saveBtn.type = "button";
    saveBtn.textContent = "Save";

    const delBtn = document.createElement("button");
    delBtn.className = "btn warn btn-sm";
    delBtn.type = "button";
    delBtn.style.marginLeft = ".5rem";
    delBtn.textContent = "Delete";

    saveBtn.addEventListener("click", async () => {
      if (saveBtn.disabled) return;

      let parsed;
      try {
        if (type === "bool" || type === "boolean") {
          parsed = valueEl.value === "true";
        } else if (type === "int" || type === "integer") {
          parsed = valueEl.value === "" ? null : parseInt(valueEl.value, 10);
          if (parsed !== null && Number.isNaN(parsed)) throw new Error("Not a valid integer");
        } else if (type === "float" || type === "number") {
          parsed = valueEl.value === "" ? null : parseFloat(valueEl.value);
          if (parsed !== null && Number.isNaN(parsed)) throw new Error("Not a valid number");
        } else if (type === "dict" || type === "list" || type === "object" || type === "array") {
          parsed = parseJsonInput(valueEl.value); // expects JSON
        } else {
          // default string
          parsed = valueEl.value;
        }
      } catch (e) {
        toast(`Invalid value for ${key}: ${e.message}`, "error");
        return;
      }

      const oldText = saveBtn.textContent;
      saveBtn.disabled = true;
      delBtn.disabled = true;
      saveBtn.textContent = "Saving…";

      try {
        await patchConfig(key, parsed, chk.checked, type);
        toast(`Updated ${key}`, "success");
        await window.loadConfiguration?.();
      } catch (e) {
        toast(`Failed to update ${key}: ${e.message}`, "error");
      } finally {
        saveBtn.disabled = false;
        delBtn.disabled = false;
        saveBtn.textContent = oldText;
        refreshConfig();
      }
    });

    delBtn.addEventListener("click", async () => {
      if (delBtn.disabled) return;
      if (!confirm(`Delete config '${key}'?`)) return;

      const oldText = delBtn.textContent;
      saveBtn.disabled = true;
      delBtn.disabled = true;
      delBtn.textContent = "Deleting…";

      try {
        // You need to implement this API call (or reuse PATCH with value=null, etc.)
        await window.deleteConfig?.(key, chk.checked);
        toast(`Deleted ${key}`, "success");
        await window.loadConfiguration?.();
      } catch (e) {
        toast(`Failed to delete ${key}: ${e.message}`, "error");
      } finally {
        saveBtn.disabled = false;
        delBtn.disabled = false;
        delBtn.textContent = oldText;
        refreshConfig();
      }
    });

    tdAction.appendChild(saveBtn);
    tdAction.appendChild(delBtn);

    tr.appendChild(tdKey);
    tr.appendChild(tdVal);
    tr.appendChild(tdPersist);
    tr.appendChild(tdAction);

    tbody.appendChild(tr);
  });
}
function isNumeric(value) {
  return !isNaN(value) && !isNaN(parseFloat(value));
}

  function wireConfigUI() {
    console.log("Wiring config ui...");

    document.getElementById("config-search")?.addEventListener("input", () => {
      renderConfigTable(window.__config_cache || {});
    });
    
    document.getElementById("config-new-save").addEventListener("click", async () => {
      const keyEl = document.getElementById("config-new-key");
      const valEl = document.getElementById("config-new-value");
      const persistEl = document.getElementById("config-new-persist");
      const btn = document.getElementById("config-new-save");
      let key = String(keyEl?.value || "").trim();
      if (!key) key = "None";
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Saving…";
      let type;
      const val = String(valEl).trim();

      if (val === "True" || val === "False")
          type = "bool";

      else if (!isNaN(val) && Number.isInteger(Number(val)))
          type = "int";

      else if (!isNaN(val) && !Number.isInteger(Number(val)))
          type = "float";

      else if (val === "None" || val === "null")
          type = "none";

      else if (val.startsWith("[") && val.endsWith("]"))
          type = "list";

      else if (val.startsWith("{") && val.endsWith("}"))
          type = "dict";

      else
          type = "str";
      try {
        await patchConfig(key, valEl.value, !!persistEl?.checked, type);
        toast(`Saved ${key}`, "success");
        keyEl.value = "";
        valEl.value = "";
        persistEl.checked = false;
      } catch (e) {
        toast("❌ Failed to save: " + e.message, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = originalText;
        refreshConfig();
      }
    });
  }



async function refreshConfig() {
    const msg = await fetchConfig();
    renderConfigTable(msg);
}

wireConfigUI();

