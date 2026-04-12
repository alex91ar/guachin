// ---------- SESSIONS ----------

async function loadSessions(username) {
  try {
    let url = window.sessions_API;
    let fetchOptions = {};


    // If username is provided, use admin endpoint and include user in body
    if (username) {
      url = window.list_user_sessions_for_user_SUDO // fallback
      fetchOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: username }),
      };
    }

    const res = await fetch(url, fetchOptions);
    let data = await res.json();

    if (!res.ok || data.result === "error") {
      return handleLogout && handleLogout();
    }

    const sessions = data.message || [];
    updateSessionsUI(sessions);
  } catch (err) {
    console.error("Failed to load sessions:", err);
    showToast("❌ Failed to load sessions.", "error");
  }
}

function formatUnix(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleString(); // uses browser locale/timezone
}

function isUnixValid(ts, nowSeconds) {
  return !!ts && ts > nowSeconds;
}

function makeStatusPill(isValid, validText = "Valid", expiredText = "Expired") {
  const pill = document.createElement("span");
  pill.className = "status-pill " + (isValid ? "valid" : "expired");
  pill.textContent = isValid ? validText : expiredText;
  return pill;
}

function updateSessionsUI(sessions) {
  const wrapper = document.getElementById("sessions-table-wrapper");
  const tbody = document.getElementById("sessions-tbody");
  const emptyMsg = document.getElementById("sessions-empty");
  if (!wrapper || !tbody || !emptyMsg) return;

  tbody.innerHTML = "";

  if (!sessions || sessions.length === 0) {
    wrapper.classList.add("hidden");
    emptyMsg.classList.remove("hidden");
    return;
  }

  wrapper.classList.remove("hidden");
  emptyMsg.classList.add("hidden");


  const nowSeconds = Math.floor(Date.now() / 1000);
  sessions.forEach((s) => {
    const tr = document.createElement("tr");

    // ID
    const idTd = document.createElement("td");
    idTd.textContent = s.id || "—";

    // User agent
    const uaTd = document.createElement("td");
    uaTd.textContent = s.user_agent || "Unknown";

    // Source IP
    const ipTd = document.createElement("td");
    ipTd.textContent = s.source_ip || "Unknown";

    // Expiry dates
    const accessExpTd = document.createElement("td");
    accessExpTd.textContent = formatUnix(s.valid_until);

    const refreshExpTd = document.createElement("td");
    refreshExpTd.textContent = formatUnix(s.valid_until_refresh);

    // Status pills
    const accessStatusTd = document.createElement("td");
    const accessValid = isUnixValid(s.valid_until, nowSeconds);
    accessStatusTd.appendChild(makeStatusPill(accessValid));

    const refreshStatusTd = document.createElement("td");
    const refreshValid = isUnixValid(s.valid_until_refresh, nowSeconds);
    refreshStatusTd.appendChild(makeStatusPill(refreshValid));

    // Privilege pill
    const privilegeTd = document.createElement("td");
    const privPill = document.createElement("span");
    privPill.className =
      "priv-pill " + (s.elevated ? "priv-elevated" : "priv-standard");
    privPill.textContent = s.elevated ? "Elevated" : "Standard";
    privilegeTd.appendChild(privPill);

    // Actions
    const actionTd = document.createElement("td");
    actionTd.className = "actions-cell";

    // Expire access button
    const expireAccessBtn = document.createElement("button");
    expireAccessBtn.type = "button";
    expireAccessBtn.textContent = "Expire access";
    expireAccessBtn.className = "btn danger btn-sm";
    expireAccessBtn.disabled = !accessValid;
    expireAccessBtn.addEventListener("click", () =>
      expireSession(s, "access")
    );

    // Expire refresh button
    const expireRefreshBtn = document.createElement("button");
    expireRefreshBtn.type = "button";
    expireRefreshBtn.textContent = "Expire refresh";
    expireRefreshBtn.className = "btn danger btn-sm";
    expireRefreshBtn.disabled = !refreshValid;
    expireRefreshBtn.addEventListener("click", () =>
      expireSession(s, "refresh")
    );

    actionTd.appendChild(expireAccessBtn);
    actionTd.appendChild(expireRefreshBtn);

    tr.appendChild(idTd);
    tr.appendChild(uaTd);
    tr.appendChild(ipTd);
    tr.appendChild(accessExpTd);
    tr.appendChild(refreshExpTd);
    tr.appendChild(accessStatusTd);
    tr.appendChild(refreshStatusTd);
    tr.appendChild(privilegeTd);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });
}



async function expireSession(session, kind) {
  try {
    const res = await fetch(window.expire_session_API, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ id: session.id, token_type:kind })
    });

    let data = await res.json();

    if (!res.ok || data.result === "error") {
      throw new Error(data.message || "Unknown error");
    }

    showToast("✅ Session expired.", "success");
    await loadSessions();
  } catch (err) {
    console.error("Failed to expire session:", err);
    showToast("❌ Failed to expire session: " + err.message, "error");
  }
}
