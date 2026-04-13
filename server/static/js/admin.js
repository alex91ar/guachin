const $ = (sel, ctx = document) => (ctx || document).querySelector(sel);
const $$ = (sel, ctx = document) => Array.from((ctx || document).querySelectorAll(sel));

async function wireSudo() {
  const sudoModal = document.getElementById("sudo-modal");
  const sudoForm  = document.getElementById("sudo-form");
  const otpInput  = document.getElementById("sudo-otp");
  function openSudoModal() {
    sudoModal?.classList.remove("hidden");
    sudoModal?.removeAttribute("hidden");
    otpInput?.focus();
  }
  function closeSudoModal() {
    sudoModal?.classList.add("hidden");
    sudoModal?.setAttribute("hidden", "");
    sudoForm?.reset();
  }
  window.openSudoModal = openSudoModal;
  document.querySelectorAll('[data-close="sudo-modal"]').forEach(btn => {
    btn.addEventListener("click", closeSudoModal);
  });
  // Manual entry (used when 2FA is enabled or auto-sudo failed)
  sudoForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const otp = otpInput?.value.trim();
    if (!otp) return showToast("Enter your 2FA code.", "error");
    try {
      const res = await fetch(window.get_sudo_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ otp}),
      });
      let json = {};
      try { json = await res.json(); } catch {}
      if (json.result === "success") {
        if (typeof new_session === "function") {
          new_session(json.message.access_jwt, json.message.refresh_jwt, json.message.user_obj);
        }
        showToast("Sudo verified!", "success");
        closeSudoModal();
        sessionStorage.setItem("__sudo_ok", "1");
        location.reload(); // 🔥 reload after manual sudo
        return;
      }
      showToast(json.message || "Invalid code.", "error");
    } catch (error) {
      showToast(error.message || "Verification failed.", "error");
    }
  });
}

window.loadSystemInfo = async function loadSystemInfo() {
    try {
      let data = await fetch(window.get_system_info_SUDO);
      data = await data.json();
      $("#sys-hostname").textContent = data.hostname;
      $("#sys-platform").textContent = data.platform;
      $("#sys-python").textContent = data.python;
      $("#sys-uptime").textContent = data.uptime;
      $("#sys-cpu").textContent = data.cpu;
      $("#sys-load").textContent = data.load;
      $("#sys-mem").textContent = data.mem;
    } catch {
      showToast("Failed to load system info", "error");
    }
  };
(function () {
  /* ---------------- TOAST SYSTEM ---------------- */
  window.showToast = function (msg, type = "info") {
    let container = $("#toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      Object.assign(container.style, {
        position: "fixed",
        top: "1rem",
        right: "1rem",
        zIndex: "9999"
      });
      document.body.append(container);
    }
    const toast = document.createElement("div");
    toast.textContent = msg;
    toast.className = `toast ${type}`;
    Object.assign(toast.style, {
      background: type === "error" ? "#ff4d4d" : type === "success" ? "#4caf50" : "#333",
      color: "#fff",
      padding: "10px 16px",
      borderRadius: "8px",
      marginTop: "8px",
      boxShadow: "0 4px 8px rgba(0,0,0,0.15)",
      opacity: "0",
      transform: "translateY(-10px)",
      transition: "opacity .3s, transform .3s",
    });
    container.append(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateY(0)";
    });
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-10px)";
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  };
  /* ---------------- INIT ---------------- */
  document.addEventListener("DOMContentLoaded", async () => {
    // one-time toast after reload
    if (sessionStorage.getItem("__sudo_ok") === "1") {
      sessionStorage.removeItem("__sudo_ok");
      showToast("Sudo active", "success");
    }
  document.getElementById("reload-everything-btn")?.addEventListener("click", async () => {
  });
    bindTabs();
    bindCloseButtons();
    
  });

  /* ---------------- TABS ---------------- */
  function bindTabs() {
    $$(".tabs .tab").forEach((tab) =>
      tab.addEventListener("click", () => {
        $$(".tab").forEach((b) => b.classList.remove("active"));
        tab.classList.add("active");
        $$(".tab-panel").forEach((p) => p.classList.remove("show"));
        $("#tab-" + tab.dataset.tab).classList.add("show");
        
      })
    );
  }
  /* ---------------- MODAL CLOSE ---------------- */
  function bindCloseButtons() {
    $$("[data-close]").forEach((b) =>
      b.addEventListener("click", () =>
        $("#" + b.dataset.close)?.setAttribute("hidden", "")
      )
    );
  }
})();


/* ---------------- TERMINAL ---------------- */
function openLiveShell() {
  const token = localStorage.getItem("access_jwt");
  const csrf_token = localStorage.getItem("csrf-token");
  if (!token || !csrf_token) return alert("Missing tokens.");
  const term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    theme: { background: "#111", foreground: "#eee" },
  });
  document.getElementById("terminal").innerHTML = "";
  term.open(document.getElementById("terminal"));
  term.reset();
  term.write("Connecting...\r\n");
  const ws = new WebSocket(window.shell_ws_API);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", access_jwt: token, csrf_token }));
  };
  ws.onmessage = e => term.write(e.data);
  ws.onclose = () => term.write("\r\n[disconnected]\r\n");
  ws.onerror = e => term.write(`\r\n[error] ${e}\r\n`);
  term.onData(data => ws.send(data));
  window.addEventListener("resize", () => {
    const { cols, rows } = term;
    ws.send(`__resize__:${cols}:${rows}`);
  });
}
/* =====================================================
   USERS MODULE
   ===================================================== */
(function () {
  /* ---------------- TOASTS ---------------- */
  function showToast(msg, type = "info") {
    let container = $("#toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      Object.assign(container.style, {
        position: "fixed",
        top: "1rem",
        right: "1rem",
        zIndex: "9999",
      });
      document.body.append(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    Object.assign(toast.style, {
      background: type === "error" ? "#ff4d4d" : type === "success" ? "#4caf50" : "#333",
      color: "#fff",
      padding: "10px 16px",
      borderRadius: "8px",
      marginTop: "8px",
      boxShadow: "0 4px 8px rgba(0,0,0,0.15)",
      opacity: "0",
      transform: "translateY(-10px)",
      transition: "opacity .3s, transform .3s",
    });
    container.append(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateY(0)";
    });
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-10px)";
      setTimeout(() => toast.remove(), 280);
    }, 3000);
  }
async function ensureRolesLoaded() {
   if (!Array.isArray(window.cachedRoles) || window.cachedRoles.length === 0) { 
    await loadRoles(); 
  } }
  /* ---------------- INIT ---------------- */
  document.addEventListener("DOMContentLoaded", () => {
    // open "add user" modal
    $("#add-user-btn") && ($("#add-user-btn").onclick = async () => {
      const modal = $("#add-user-modal");
      if (!modal) return;
      modal.removeAttribute("hidden");
      await ensureRolesLoaded();
      setupRoleSelectors([], "add");          // fills available roles list
      bindDualSelectorButtons("add");         // wires arrow buttons correctly
    });

    // delegated click handler (buttons inside table & modals)
    document.body.addEventListener("click", async (e) => {
      const target = e.target?.closest?.("[data-edit],[data-action],[data-close]");
      if (!target) return;
      // close modals
      if (target.dataset.close) {
        const id = target.dataset.close;
        const modal = document.getElementById(id);
        modal && modal.setAttribute("hidden", "");
        return;
      }
      // EDIT USER
      if (target.dataset.edit === "user") {
        let data;
        try {
          const raw = target.dataset.json || "{}";
          data = JSON.parse(raw);
        } catch {
          try { data = JSON.parse(decodeURIComponent(target.dataset.json || "%7B%7D")); }
          catch { showToast("Invalid user payload", "error"); return; }
        }
        const modal = $("#edit-user-modal");
        if (!modal) { showToast("Edit modal missing", "error"); return; }
        modal.removeAttribute("hidden");
        modal.querySelector(`[name="id"]`).value = data.id;
        modal.querySelector(`[name="email"]`).value = data.email ?? "";
        await ensureRolesLoaded();
        const preselected = Array.isArray(data.roles) ? data.roles : [];
        setupRoleSelectors(preselected, "edit");
        bindDualSelectorButtons("edit");
        return;
      }
      if (target.dataset.target === "user") {
        let data;
        try {
          const raw = target.dataset.json || "{}";
          data = JSON.parse(raw);
        } catch {
          try { data = JSON.parse(decodeURIComponent(target.dataset.json || "%7B%7D")); }
          catch { showToast("Invalid user payload", "error"); return; }
        }
        const modal = $("#add-user-modal");
        if (!modal) { showToast("Add modal missing", "error"); return; }
        modal.removeAttribute("hidden");
        modal.querySelector(`[name="id"]`).value = data.id;
        modal.querySelector(`[name="email"]`).value = data.email ?? "";
        await ensureRolesLoaded();
        const preselected = Array.isArray(data.roles) ? data.roles : [];
        setupRoleSelectors(preselected, "add");
        bindDualSelectorButtons("add");
        return;
      }
      // OPEN CHANGE PASSWORD MODAL
      if (target.dataset.action === "change_password" && target.dataset.name) {
        const modal = $("#change-password-modal");
        if (!modal) { showToast("Change password modal missing", "error"); return; }
        modal.removeAttribute("hidden");
        modal.querySelector(`[name="id"]`).value = target.dataset.name;
        // focus password field
        modal.querySelector(`[name="password"]`)?.focus();
        return;
      }
      // USER ACTIONS via /action (delete, expire, disable_twofa)
      if (target.dataset.action && target.dataset.name) {
        const username = target.dataset.name;
        const action = target.dataset.action;
        const modal = document.getElementById("sessions-modal");
        if(action == "sessions"){
          await loadSessions(username);
          modal.classList.remove("hidden");
          modal.hidden = false;
          return;
        }
        if (!confirm(`Perform '${action}' on ${username}?`)) return;
        try {
          await fetch(window.do_user_action_SUDO, {
            method: "PUT",
            body: JSON.stringify({ id: username, action }),
          });
          showToast(`Action '${action}' executed for ${username}`, "success");
          loadUsers();
        } catch (err) {
          showToast(err.message, "error");
        }
      }
    });
    // forms
    bindForms();
    // first load
  });
  /* ---------------- LOAD USERS ---------------- */
  async function loadUsers() {
    // expose helpers globally if other modules need them
    window.$ = $; window.$$ = $$;
    let data = await fetch(window.list_users_SUDO); data = await data.json();
    // API sometimes returns in 'users' or 'message'
    const users = data.users || data.message || [];
    const tbody = $("#users-table tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    users.forEach((u) => {
      const actions = [
        `<button class="btn subtle" data-edit="user" data-json='${JSON.stringify(u)}'>Edit</button>`,
        `<button class="btn warn" data-action="delete" data-name="${u.id}">Delete</button>`,
        `<button class="btn subtle" data-action="sessions" id="open-sessions-modal" data-name="${u.id}">Sessions</button>`,
        `<button class="btn subtle" data-action="change_password" data-name="${u.id}">Change Password</button>`,
      ];
      if (u.twofa_enabled) {
        actions.push(`<button class="btn subtle" data-action="disable_twofa" data-name="${u.id}">Disable 2FA</button>`);
      }
      tbody.insertAdjacentHTML(
        "beforeend",
        `
        <tr>
          <td>${u.id}</td>
          <td>${u.email ?? "—"}</td>
          <td>${(u.roles || []).join(", ")}</td>
          <td>${u.twofa_enabled ? "✅" : "❌"}</td>
          <td class="right">${actions.join(" ")}</td>
        </tr>`
      );
    });
  }
  window.loadUsers = loadUsers; // optional global
  /* ---------------- ROLE SELECTORS (Users) ---------------- */
  function setupRoleSelectors(preselected = [], prefix = "add") {
    const allRoles = window.cachedRoles || [];
    const available = document.querySelector(`#available-roles-${prefix}`);
    const selected = document.querySelector(`#selected-roles-${prefix}`);
    if (!available || !selected) return;
    available.innerHTML = "";
    selected.innerHTML = "";
    allRoles.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = r.id;
      if (preselected.includes(r.id)) selected.append(opt);
      else available.append(opt);
    });
  }
  function bindDualSelectorButtons(prefix) {
  // Your HTML uses special IDs for the "add" modal:
  // add-role-to-user / remove-role-from-user
  const addBtnSel = prefix === "add" ? "#add-role-to-user" : `#add-role-to-${prefix}`;
  const remBtnSel = prefix === "add" ? "#remove-role-from-user" : `#remove-role-from-${prefix}`;
  const addBtn = document.querySelector(addBtnSel);
  const removeBtn = document.querySelector(remBtnSel);
  const available = document.querySelector(`#available-roles-${prefix}`);
  const selected  = document.querySelector(`#selected-roles-${prefix}`);
  if (!addBtn || !removeBtn || !available || !selected) return;
  // Rebind safely by cloning (avoids stacking listeners)
  const addClone = addBtn.cloneNode(true);
  const remClone = removeBtn.cloneNode(true);
  addBtn.replaceWith(addClone);
  removeBtn.replaceWith(remClone);
  addClone.addEventListener("click", () => {
    [...available.selectedOptions].forEach((opt) => selected.append(opt));
  });
  remClone.addEventListener("click", () => {
    [...selected.selectedOptions].forEach((opt) => available.append(opt));
  });
}

  /* ---------------- FORMS ---------------- */
  function bindForms() {
    const expireForm = $("#sessions-modal");
    if(expireForm){
    }
    // Add User
    const addForm = $("#add-user-form");
    const addOverlay = $("#add-user-modal");
    if (addForm) {
      addForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          const f = Object.fromEntries(new FormData(addForm));
          f.roles = [...$("#selected-roles-add").options].map((opt) => opt.value);
          await fetch(window.create_user_SUDO, { method: "POST", body: JSON.stringify(f) });
          showToast("User created successfully", "success");
          addForm.reset();
          addOverlay.closest(".modal-backdrop")?.setAttribute("hidden", "");
          addOverlay.hidden = true;
          loadUsers();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    }
    // Edit User
    const editForm = $("#edit-user-form");
    const editModal = $("#edit-user-modal");
    if (editForm) {
      editForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          const f = Object.fromEntries(new FormData(editForm));
          f.roles = [...$("#selected-roles-edit").options].map((opt) => opt.value);
          await fetch(window.update_user_SUDO, { method: "PUT", body: JSON.stringify(f) });
          showToast("User updated", "success");
          editForm.closest(".modal-backdrop")?.setAttribute("hidden", "");
          loadUsers();
          editModal.hidden = true;
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    }
    // Change Password
    const pwForm = $("#change-password-form");
    if (pwForm) {
      pwForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          const f = Object.fromEntries(new FormData(pwForm));
          if (!f.password || String(f.password).length < 4) {
            showToast("Password too short", "error");
            return;
          }
          await fetch(window.do_user_action_SUDO, {
            method: "PUT",
            body: JSON.stringify({ id: f.id, action: "change_password", value: f.password }),
          });
          showToast("Password updated successfully", "success");
          pwForm.reset();
          pwForm.closest(".modal-backdrop")?.setAttribute("hidden", "");
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    }
  }
})();
/* =====================================================
   ROLES MODULE — fix preselected actions in edit modal
   ===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  // expose helpers if needed elsewhere
  window.$ = $;
  window.$$ = $$;
  // Add Role
  $("#add-role-btn").onclick = async () => {
    await loadActions();
    $("#add-role-modal").removeAttribute("hidden");
    setupActionSelectors([], "add");
    bindActionDualButtons("add");
  };
  // Delegated clicks
  document.body.addEventListener("click", async (e) => {
    const btn = e.target?.closest?.("[data-edit],[data-delete],[id]") || e.target;
    /* -------- EDIT ROLE -------- */
    if (btn.dataset && btn.dataset.edit === "role") {
      let data;
      try { data = JSON.parse(btn.dataset.json); }
      catch { showToast("Invalid role payload", "error"); return; }
      await loadActions();
      const modal = $("#edit-role-modal");
      modal.removeAttribute("hidden");
      modal.querySelector(`[name="id"]`).value = data.id;
      modal.querySelector(`[name="description"]`).value = data.description || "";
      // Preselected actions: array of IDs or array of {id,...}
      const preselected = Array.isArray(data.actions)
        ? data.actions.map(a => (a && typeof a === "object" ? a.id : a))
        : [];
      setupActionSelectors(preselected, "edit");
      bindActionDualButtons("edit");
      return;
    }
    /* -------- DELETE ROLE -------- */
    if (btn.dataset && btn.dataset.delete === "role") {
      const id = btn.dataset.id;
      if (!confirm(`Delete role '${id}'?`)) return;
      await deleteRole(id);
      return;
    }
    if (btn.dataset && btn.dataset.delete === "passkey") {
      const id = btn.dataset.id;
      if (!confirm(`Delete passkey '${id}'?`)) return;
      await deletePasskey(id);
      return;
    }
    /* -------- Fallback dual selector buttons (if needed) -------- */
    if (btn.id === "add-action-to-role" || btn.id === "add-action-to-edit") {
      const prefix = btn.id.includes("edit") ? "edit" : "add";
      moveOptions(`#available-actions-${prefix}`, `#selected-actions-${prefix}`);
      return;
    }
    if (btn.id === "remove-action-from-role" || btn.id === "remove-action-from-edit") {
      const prefix = btn.id.includes("edit") ? "edit" : "add";
      moveOptions(`#selected-actions-${prefix}`, `#available-actions-${prefix}`);
      return;
    }
  });
  $("#add-role-form").onsubmit = submitAddRole;
  $("#edit-role-form").onsubmit = submitEditRole;
});


/* ---------------- LOAD ROLES (table) ---------------- */
window.loadRoles = async function () {
  let data = await fetch(window.list_roles_SUDO);
  data = await data.json();
  const roles = data.roles || data.message || [];
  window.cachedRoles = roles;
  const tbody = $("#roles-table tbody");
  tbody.innerHTML = "";
  roles.forEach((r) => {
    tbody.insertAdjacentHTML(
      "beforeend",
      `
      <tr>
        <td>${r.id}</td>
        <td>${r.description || "—"}</td>
        <td>${Array.isArray(r.actions) ? r.actions.length : 0}</td>
        <td class="right">
          <button class="btn subtle" data-edit="role" data-json='${JSON.stringify(r)}'>Edit</button>
          <button class="btn warn" data-delete="role" data-id="${r.id}">Delete</button>
        </td>
      </tr>`
    );
  });
};
/* ---------------- LOAD PASSKEYS (table) ---------------- */
window.loadPasskeys = async function () {
  const empty = document.getElementById("passkeys-empty");
  const wrapper = document.getElementById("passkeys-table-wrapper");
  const tbody = document.querySelector("#passkeys-table tbody");
  tbody.innerHTML = "";
  empty?.classList.add("hidden");
  wrapper?.classList.add("hidden");
  try {
    const data = await apiListPasskeys();
    if (!Array.isArray(data) || data.length === 0) {
      empty?.classList.remove("hidden");
      return;
    }
    wrapper?.classList.remove("hidden");
    data.forEach((p) => {
      tbody.insertAdjacentHTML(
        "beforeend",
        `
        <tr>
          <td>${p.id ?? "—"}</td>
          <td>${p.user_id ?? "—"}</td>
          <td>${p.credential_id ?? "—"}</td>
          <td>${p.sign_count ?? "—"}</td>
          <td class="right">
          <button class="btn warn" data-delete="passkey" data-id="${p.id}">Delete</button>
          </td>
        </tr>`
      );
    });
  } catch (e) {
    console.error(e);
    empty?.classList.remove("hidden");
  }
};

/* load---------------- ACTION SELECTORS (dual lists) ---------------- */
function setupActionSelectors(preselected = [], prefix = "add") {
  const allActions = window.cachedActions || [];
  const available = document.querySelector(`#available-actions-${prefix}`);
  const selected = document.querySelector(`#selected-actions-${prefix}`);
  if (!available || !selected) return;
  available.innerHTML = "";
  selected.innerHTML = "";
  const pre = new Set((preselected || []).map(String)); // normalize to strings
  allActions.forEach((a) => {
    const id = String(a.id);
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = `${a.method} ${a.path}`;
    (pre.has(id) ? selected : available).append(opt);
  });
}
/* Bind arrow buttons every time a modal opens */
function bindActionDualButtons(prefix) {
  const addBtn = document.querySelector(`#add-action-to-${prefix}`);
  const removeBtn = document.querySelector(`#remove-action-from-${prefix}`);
  if (!addBtn || !removeBtn) return;
  // Rebind safely by cloning to avoid duplicate listeners
  const addClone = addBtn.cloneNode(true);
  const remClone = removeBtn.cloneNode(true);
  addBtn.replaceWith(addClone);
  removeBtn.replaceWith(remClone);
  addClone.addEventListener("click", () => {
    moveOptions(`#available-actions-${prefix}`, `#selected-actions-${prefix}`);
  });
  remClone.addEventListener("click", () => {
    moveOptions(`#selected-actions-${prefix}`, `#available-actions-${prefix}`);
  });
}
/* ---------------- SUBMIT HANDLERS ---------------- */
async function submitAddRole(e) {
  e.preventDefault();
  try {
    const f = Object.fromEntries(new FormData(e.target));
    f.actions = [...$("#selected-actions-add").options].map((opt) => opt.value);
    await fetch(window.create_role_SUDO, { method: "POST", body: JSON.stringify(f) });
    showToast("Role created successfully", "success");
    e.target.closest(".modal-backdrop")?.setAttribute("hidden", "");
    loadRoles();
  } catch (err) {
    showToast(err.message, "error");
  }
}
async function submitEditRole(e) {
  e.preventDefault();
  try {
    const formEl = e.target;
    const f = Object.fromEntries(new FormData(formEl));
    const actions = [...$("#selected-actions-edit").options].map(opt => opt.value);
    const payload = {
      id: f.id,
      description: f.description,   // required by backend
      actions
    };
    let url = window.update_role_SUDO; 
    // ^ pick whatever your generator exposes, otherwise common fallback
    await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    showToast("Role updated", "success");
    formEl.closest(".modal-backdrop")?.setAttribute("hidden", "");
    loadRoles();
    const modal = document.getElementById("edit-role-modal");
    modal.hidden = true;
  } catch (err) {
    console.error(err);
    showToast(err.message || "Failed to update role", "error");
  }
}

/* ---------------- DELETE ROLE ---------------- */
async function deleteRole(id) {
  try {
      await fetch(window.delete_role_SUDO, { method: "POST", body: JSON.stringify({ id: id }) });
    showToast(`Role '${id}' deleted`, "success");
    loadRoles();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deletePasskey(id) {
  try {
      await fetch(window.delete_passkey_SUDO, { method: "POST", body: JSON.stringify({ id: id }) });
    showToast(`Passkey '${id}' deleted`, "success");
    loadPasskeys();
  } catch (err) {
    showToast(err.message, "error");
  }
}

/* ---------------- HELPERS ---------------- */
function moveOptions(fromSel, toSel) {
  const from = document.querySelector(fromSel);
  const to = document.querySelector(toSel);
  if (!from || !to) return;
  [...from.selectedOptions].forEach((opt) => to.append(opt));
}
/* =====================================================
   ACTIONS MODULE
   ==================================================X=== */

/* ---------------- LOAD ACTIONS ---------------- */


function activateTab(tabName) {
  // deactivate all tabs
  document.querySelectorAll(".tab").forEach(btn => {
    btn.classList.remove("active");
  });
  // hide all tab panels
  document.querySelectorAll(".tab-content").forEach(panel => {
    panel.classList.add("hidden");
  });
  // activate target tab button
  const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
  if (!tab) return;
  tab.classList.add("active");
  // show target panel
  const panel = document.getElementById(`tab-${tabName}`);
  panel?.classList.remove("hidden");
  // run tab-specific loaders
  switch (tabName) {
    case "users":
      loadUsers();
      break;
    case "passkeys":
      loadPasskeys();
      break;
    case "roles":
      loadActions();
      loadRoles();
      break;
    case "actions":
      loadActions();
      break;
    case "system":
      loadSystemInfo();
      break;
    case "logs":
      refreshLogs();
      break;
    case "configuration":
      refreshConfig();
      break;
    case "filemanager":
      break;
  }
}
function openModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.hidden = false;
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.hidden = true;
}
// generic wiring for any [data-open] / [data-close]
document.addEventListener("click", (e) => {
  const openId = e.target?.closest?.("[data-open]")?.getAttribute("data-open");
  if (openId) openModal(openId);
  const closeId = e.target?.closest?.("[data-close]")?.getAttribute("data-close");
  if (closeId) closeModal(closeId);
});
function notifyPasskeys(message, type = "info") {
  if (typeof showToast === "function") return showToast(message, type);
  if (typeof showToast === "function") return showToast(message, type === "danger" ? "error" : type);
  try { alert(message); } catch (_) { console.log(`[${type}] ${message}`); }
}
async function apiCreatePasskey(payload) {
  const url = window.create_passkey_SUDO; // set this in dashboard.html
  if (!url) throw new Error("Missing window.create_passkey_SUDO");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.result === "error") {
    throw new Error(data.message || `${res.status}`);
  }
  return data;
}
function setupAddPasskeyModal() {
  const form = document.getElementById("add-passkey-form");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {
      user_id: Number(fd.get("user_id")),
      credential_id: String(fd.get("credential_id") || "").trim(),
      public_key: String(fd.get("public_key") || "").trim(),
      sign_count: Number(fd.get("sign_count") ?? 0),
    };
    // tiny validation
    if (!payload.user_id || !payload.credential_id || !payload.public_key) {
      notifyPasskeys("Please fill all required fields.", "danger");
      return;
    }
    try {
      await apiCreatePasskey(payload);
      notifyPasskeys("✅ Passkey created.", "success");
      form.reset();
      closeModal("add-passkey-modal");
      // refresh table
      if (typeof loadPasskeys === "function") await loadPasskeys();
      if(typeof setResult === "function") setResult("Passkey deleted successfully.")
    } catch (err) {
      console.error(err);
      notifyPasskeys(`❌ Failed to create passkey: ${err.message}`, "danger");
    }
  });
}

function parseDatasetJson(raw) {
  if (!raw) return null;
  try {
    // your HTML stores escaped JSON in attribute; unescape basic entities first
    const s = String(raw)
      .replaceAll("&quot;", '"')
      .replaceAll("&#039;", "'")
      .replaceAll("&lt;", "<")
      .replaceAll("&gt;", ">")
      .replaceAll("&amp;", "&");
    return JSON.parse(s);
  } catch (e) {
    // fallback: maybe it wasn't escaped (or already decoded)
    try { return JSON.parse(raw); } catch { return null; }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupAddPasskeyModal();
});
