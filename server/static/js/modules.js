// static/js/modules.js

// ---------- NOTIFY HELPERS ----------
let editModuleCodeEditor = null;

function initEditModuleCodeEditor() {
  const editorEl = document.getElementById("edit-module-code-editor");
  const form = document.getElementById("edit-module-form");
  const textarea = form?.elements?.code;

  if (!editorEl || !textarea) return;

  if (typeof ace === "undefined") {
    console.error("Ace editor is not loaded.");
    editorEl.innerHTML = "<div style='padding:1rem;color:#c00;'>Ace editor not loaded.</div>";
    return;
  }

  if (editModuleCodeEditor) return;

  editModuleCodeEditor = ace.edit(editorEl);
  editModuleCodeEditor.setTheme("ace/theme/github_dark");
  editModuleCodeEditor.session.setMode("ace/mode/python");
  editModuleCodeEditor.setOptions({
    fontSize: "14px",
    tabSize: 4,
    useSoftTabs: true,
    showPrintMargin: false,
    wrap: true,
  });

  editModuleCodeEditor.session.on("change", () => {
    textarea.value = editModuleCodeEditor.getValue();
  });
}
function notifyModules(message, type = "info") {
  if (typeof showAlert === "function") return showAlert(message, type);
  if (typeof showToast === "function") return showToast(message, type === "danger" ? "error" : type);
  try {
    alert(message);
  } catch (_) {
    console.log(`[${type}] ${message}`);
  }
}

// ---------- HELPERS ----------

function safeModuleText(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch (_) {
    return String(v);
  }
}

function truncateModuleText(s, n = 120) {
  const str = safeModuleText(s);
  if (str.length <= n) return str;
  return str.slice(0, n) + "…";
}

function parseJSONInput(value, fallback = []) {
  const raw = (value || "").trim();
  if (!raw) return fallback;
  return JSON.parse(raw);
}

function uniqueSortedStrings(values) {
  return [...new Set((values || []).filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b));
}

function getSelectedOptionsValues(selectEl) {
  if (!selectEl) return [];
  return Array.from(selectEl.options).map((opt) => opt.value);
}

function moveSelectedOptions(fromSelect, toSelect) {
  if (!fromSelect || !toSelect) return;

  const selected = Array.from(fromSelect.selectedOptions);
  selected.forEach((opt) => {
    toSelect.appendChild(opt);
  });

  sortSelectOptions(fromSelect);
  sortSelectOptions(toSelect);
}

function sortSelectOptions(selectEl) {
  if (!selectEl) return;
  const options = Array.from(selectEl.options).sort((a, b) => a.value.localeCompare(b.value));
  selectEl.innerHTML = "";
  options.forEach((opt) => selectEl.appendChild(opt));
}

function fillSelect(selectEl, values) {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  uniqueSortedStrings(values).forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    selectEl.appendChild(opt);
  });
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add("hidden");
  modal.hidden = true;
  document.body.style.overflow = "";
}

// ---------- API ----------

async function apiGetAllModules() {
  const res = await fetch(window.list_modules_SUDO, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  const data = await res.json();
  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }

  return data.message || [];
}

async function apiCreateModule(payload) {
  const res = await fetch(window.create_module_SUDO, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }

  return data;
}

async function apiUpdateModule(payload) {
  const res = await fetch(window.update_module_SUDO, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }

  return data;
}

async function apiDeleteModule(name) {
  const res = await fetch(window.delete_module_SUDO, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ name }),
  });

  const data = await res.json();
  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }

  return data;
}

// ---------- STATE ----------

let _allModules = [];

// ---------- RENDERING ----------

function renderModules(rows) {
  const tbody = document.getElementById("modules-tbody");
  const empty = document.getElementById("modules-empty");
  const table = document.getElementById("modules-table");

  if (!tbody) return;
  tbody.innerHTML = "";

  if (!rows || rows.length === 0) {
    table?.parentElement?.classList.add("hidden");
    empty?.classList.remove("hidden");
    return;
  }

  table?.parentElement?.classList.remove("hidden");
  empty?.classList.add("hidden");

  rows.forEach((module) => {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.textContent = safeModuleText(module.name);

    const descriptionTd = document.createElement("td");
    descriptionTd.textContent = truncateModuleText(module.description, 100);
    descriptionTd.title = safeModuleText(module.description);

    const actionsTd = document.createElement("td");
    actionsTd.className = "right";
    actionsTd.innerHTML = `
      <div style="display:flex;gap:.5rem;justify-content:flex-end;flex-wrap:wrap;">
        <button type="button" class="btn small subtle">View</button>
        <button type="button" class="btn small">Edit</button>
        <button type="button" class="btn small danger">Delete</button>
      </div>
    `;

    const [viewBtn, editBtn, deleteBtn] = actionsTd.querySelectorAll("button");

    viewBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openModuleDetailsModal(module);
    });

    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditModuleModal(module);
    });

    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openDeleteModuleModal(module);
    });

    tr.appendChild(nameTd);
    tr.appendChild(descriptionTd);
    tr.appendChild(actionsTd);
    tbody.appendChild(tr);
  });
}

// ---------- FLOW ----------

function filterModules(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return _allModules;

  return _allModules.filter((module) => {
    const haystack = [
      module.name,
      module.description,
      module.code,
      ...(module.dependencies || []),
      JSON.stringify(module.params || []),
    ]
      .map((x) => safeModuleText(x).toLowerCase())
      .join(" | ");

    return haystack.includes(q);
  });
}

async function refreshModules() {
  try {
    const modules = await apiGetAllModules();
    _allModules = Array.isArray(modules) ? modules : [];
    renderModules(_allModules);
    refreshAllDependencyPickers();
  } catch (err) {
    console.error("Failed to load modules:", err);
    notifyModules(`❌ Failed to load modules: ${err.message}`, "danger");
    _allModules = [];
    renderModules([]);
  }
}

// ---------- DEPENDENCY PICKERS ----------

function getAllDependencyCandidates(excludeName = null) {
  return (_allModules || [])
    .map((m) => m.name)
    .filter((name) => name && name !== excludeName);
}

function setupDependencyPicker(availableId, selectedId, addBtnId, removeBtnId) {
  const available = document.getElementById(availableId);
  const selected = document.getElementById(selectedId);
  const addBtn = document.getElementById(addBtnId);
  const removeBtn = document.getElementById(removeBtnId);

  addBtn?.addEventListener("click", () => moveSelectedOptions(available, selected));
  removeBtn?.addEventListener("click", () => moveSelectedOptions(selected, available));
}

function populateDependencyPicker(availableId, selectedId, selectedValues, excludeName = null) {
  const selected = uniqueSortedStrings(selectedValues || []);
  const available = getAllDependencyCandidates(excludeName).filter((name) => !selected.includes(name));

  fillSelect(document.getElementById(availableId), available);
  fillSelect(document.getElementById(selectedId), selected);
}

function refreshAllDependencyPickers() {
  const addModalOpen = !document.getElementById("add-module-modal")?.classList.contains("hidden");
  const editModalOpen = !document.getElementById("edit-module-modal")?.classList.contains("hidden");

  if (addModalOpen) {
    const selected = getSelectedOptionsValues(document.getElementById("selected-dependencies-add"));
    populateDependencyPicker("available-dependencies-add", "selected-dependencies-add", selected, null);
  }

  if (editModalOpen) {
    const form = document.getElementById("edit-module-form");
    const currentName = form?.elements?.name?.value || null;
    const selected = getSelectedOptionsValues(document.getElementById("selected-dependencies-edit"));
    populateDependencyPicker("available-dependencies-edit", "selected-dependencies-edit", selected, currentName);
  }
}

// ---------- MODALS ----------

function openModuleDetailsModal(module) {
  document.getElementById("module-details-title").textContent = module.name || "Module Details";
  document.getElementById("module-details-name").textContent = module.name || "—";
  document.getElementById("module-details-description").textContent = module.description || "—";
  document.getElementById("module-details-dependencies").textContent =
    Array.isArray(module.dependencies) && module.dependencies.length
      ? module.dependencies.join(", ")
      : "—";
  document.getElementById("module-details-params").textContent =
    JSON.stringify(module.params || [], null, 2);
  document.getElementById("module-details-code").textContent = module.code || "—";

  openModal("module-details-modal");
}

function openAddModuleModal() {
  const form = document.getElementById("add-module-form");
  form?.reset();
  populateDependencyPicker("available-dependencies-add", "selected-dependencies-add", [], null);
  openModal("add-module-modal");
}

function openEditModuleModal(module) {
  const form = document.getElementById("edit-module-form");
  if (!form) return;

  form.elements.original_name.value = module.name || "";
  form.elements.name.value = module.name || "";
  form.elements.description.value = module.description || "";
  form.elements.params.value = JSON.stringify(module.params || [], null, 2);

  const codeValue = module.code || "";
  form.elements.code.value = codeValue;

  populateDependencyPicker(
    "available-dependencies-edit",
    "selected-dependencies-edit",
    module.dependencies || [],
    module.name || null
  );

  openModal("edit-module-modal");

  requestAnimationFrame(() => {
    initEditModuleCodeEditor();
    if (editModuleCodeEditor) {
      editModuleCodeEditor.setValue(codeValue, -1);
      editModuleCodeEditor.clearSelection();
      editModuleCodeEditor.resize();
      editModuleCodeEditor.focus();
    }
  });
}

function openDeleteModuleModal(module) {
  const form = document.getElementById("delete-module-form");
  if (!form) return;

  form.elements.name.value = module.name || "";
  document.getElementById("delete-module-name").textContent = module.name || "—";
  document.getElementById("delete-module-description").textContent = module.description || "—";

  openModal("delete-module-modal");
}

// ---------- FORM HANDLERS ----------

async function handleAddModuleSubmit(e) {
  e.preventDefault();
  const form = e.target;

  try {
    const payload = {
      name: form.elements.name.value.trim(),
      description: form.elements.description.value.trim(),
      params: parseJSONInput(form.elements.params.value, []),
      dependencies: getSelectedOptionsValues(document.getElementById("selected-dependencies-add")),
      code: form.elements.code.value,
    };

    await apiCreateModule(payload);
    notifyModules("Module created successfully.", "success");
    closeModal("add-module-modal");
    await refreshModules();
  } catch (err) {
    console.error(err);
    notifyModules(`Failed to create module: ${err.message}`, "danger");
  }
}

async function handleEditModuleSubmit(e) {
  e.preventDefault();
  const form = e.target;

  try {
    const originalName = form.elements.original_name.value.trim();
    const newName = form.elements.name.value.trim();

    if (originalName && originalName !== newName) {
      notifyModules("Renaming modules is not supported by the current PATCH route.", "danger");
      return;
    }
    if (editModuleCodeEditor) {
    form.elements.code.value = editModuleCodeEditor.getValue();
    }
    const payload = {
      name: newName,
      description: form.elements.description.value.trim(),
      params: parseJSONInput(form.elements.params.value, []),
      dependencies: getSelectedOptionsValues(document.getElementById("selected-dependencies-edit")),
      code: form.elements.code.value,
    };

    await apiUpdateModule(payload);
    notifyModules("Module updated successfully.", "success");
    closeModal("edit-module-modal");
    await refreshModules();
  } catch (err) {
    console.error(err);
    notifyModules(`Failed to update module: ${err.message}`, "danger");
  }
}

async function handleDeleteModuleSubmit(e) {
  e.preventDefault();
  const form = e.target;

  try {
    const name = form.elements.name.value.trim();
    await apiDeleteModule(name);
    notifyModules("Module deleted successfully.", "success");
    closeModal("delete-module-modal");
    await refreshModules();
  } catch (err) {
    console.error(err);
    notifyModules(`Failed to delete module: ${err.message}`, "danger");
  }
}

// ---------- UI WIRING ----------

function setupModulesUI() {
  document.getElementById("refresh-modules-btn")?.addEventListener("click", refreshModules);
  document.getElementById("add-module-btn")?.addEventListener("click", openAddModuleModal);

  document.getElementById("add-module-form")?.addEventListener("submit", handleAddModuleSubmit);
  document.getElementById("edit-module-form")?.addEventListener("submit", handleEditModuleSubmit);
  document.getElementById("delete-module-form")?.addEventListener("submit", handleDeleteModuleSubmit);

  setupDependencyPicker(
    "available-dependencies-add",
    "selected-dependencies-add",
    "add-dependency-to-module",
    "remove-dependency-from-module"
  );

  setupDependencyPicker(
    "available-dependencies-edit",
    "selected-dependencies-edit",
    "add-dependency-to-edit",
    "remove-dependency-from-edit"
  );

  document.getElementById("module-details-copy-code")?.addEventListener("click", async () => {
    const text = document.getElementById("module-details-code")?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(text);
      notifyModules("Copied module code.", "success");
    } catch (err) {
      console.error("Copy failed:", err);
      notifyModules("Failed to copy module code.", "danger");
    }
  });

  document.addEventListener("click", (e) => {
    const closeId = e.target?.dataset?.close;
    if (closeId) closeModal(closeId);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;

    [
      "add-module-modal",
      "edit-module-modal",
      "delete-module-modal",
      "module-details-modal",
    ].forEach((id) => {
      const modal = document.getElementById(id);
      if (modal && !modal.classList.contains("hidden")) closeModal(id);
    });
  });
}

// ---------- INIT ----------

document.addEventListener("DOMContentLoaded", async () => {
  setupModulesUI();
  initEditModuleCodeEditor();
  await refreshModules();
});