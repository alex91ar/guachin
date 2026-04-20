let currentShellSession = null;
let currentAgentId = null;
let agentsCache = [];
let refreshTimer = null;
let isLoadingAgents = false;

const SHELL_HISTORY_KEY = "agent-shell-history";
const AUTO_INTERACT_KEY = "agents-auto-interact-on-new";
let shellHistory = loadShellHistory();
let shellHistoryIndex = shellHistory.length;
let knownAgentIds = new Set();

function escapeCommand(value) {
    return String(value ?? "")
        .replaceAll("\\", "\\\\")
        .replaceAll("\r", "\\r")
        .replaceAll("\n", "\\n")
        .replaceAll("\t", "\\t");
}

async function reloadModules() {
  try {
    const res = await fetch(window.reload_modules_API, {
      method: "GET",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await res.json();

    if (!res.ok || data.result !== "success") {
      throw new Error(data.message || "Failed");
    }

    alert("Modules reloaded successfully.");
  } catch (err) {
    console.error(err);
    alert("Failed to reload modules: " + err.message);
  }
}

function loadShellHistory() {
    try {
        const raw = localStorage.getItem(SHELL_HISTORY_KEY);
        const parsed = JSON.parse(raw || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
        return [];
    }
}

function saveShellHistory() {
    try {
        localStorage.setItem(SHELL_HISTORY_KEY, JSON.stringify(shellHistory));
    } catch (_) {}
}

function addToShellHistory(command) {
    const value = String(command ?? "").trim();
    if (!value) return;

    const last = shellHistory[shellHistory.length - 1];
    if (last === value) {
        shellHistoryIndex = shellHistory.length;
        return;
    }

    const existingIndex = shellHistory.indexOf(value);
    if (existingIndex !== -1) {
        shellHistory.splice(existingIndex, 1);
    }

    shellHistory.push(value);

    const MAX_HISTORY = 200;
    if (shellHistory.length > MAX_HISTORY) {
        shellHistory = shellHistory.slice(shellHistory.length - MAX_HISTORY);
    }

    shellHistoryIndex = shellHistory.length;
    saveShellHistory();
}

function navigateShellHistory(direction, input) {
    if (!input || !shellHistory.length) return;

    if (direction === "up") {
        if (shellHistoryIndex > 0) {
            shellHistoryIndex -= 1;
        }
    } else if (direction === "down") {
        if (shellHistoryIndex < shellHistory.length) {
            shellHistoryIndex += 1;
        }
    }

    if (shellHistoryIndex >= 0 && shellHistoryIndex < shellHistory.length) {
        input.value = shellHistory[shellHistoryIndex];
    } else {
        input.value = "";
        shellHistoryIndex = shellHistory.length;
    }

    requestAnimationFrame(() => {
        const len = input.value.length;
        input.setSelectionRange(len, len);
    });
}

function resetShellHistoryPointer() {
    shellHistoryIndex = shellHistory.length;
}

function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
}

function buildAgentWsUrl(agentId) {
    return window.agent_ws_API.replace("/ws/0", "/ws/" + String(agentId));
}

function normalizeWsUrl(url) {
    if (!url) return null;

    if (url.startsWith("ws://") || url.startsWith("wss://")) {
        return url;
    }

    if (url.startsWith("/")) {
        const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${scheme}//${window.location.host}${url}`;
    }

    return url;
}

function getShellView() {
    return document.getElementById("agent-shell-view");
}

function getShellEmpty() {
    return document.getElementById("agent-shell-empty");
}

function getShellTitle() {
    return document.getElementById("agent-shell-title");
}

function getShellMeta() {
    return document.getElementById("agent-shell-meta");
}

function getShellTerminal() {
    return document.getElementById("agent-shell-terminal");
}

function getShellInput() {
    return document.getElementById("agent-shell-input");
}

function getAutoInteractButton() {
    return document.getElementById("auto-interact-toggle");
}

function isAutoInteractEnabled() {
    const value = localStorage.getItem(AUTO_INTERACT_KEY);
    if (value === null) return true; // default enabled
    return value === "true";
}

function setAutoInteractEnabled(enabled) {
    localStorage.setItem(AUTO_INTERACT_KEY, enabled ? "true" : "false");
    updateAutoInteractButton();
}

function updateAutoInteractButton() {
    const btn = getAutoInteractButton();
    if (!btn) return;

    const enabled = isAutoInteractEnabled();
    btn.textContent = `Interact on new agent: ${enabled ? "On" : "Off"}`;
    btn.classList.toggle("active", enabled);
}

function focusShellInput() {
    const input = getShellInput();
    if (!input) return;

    requestAnimationFrame(() => {
        input.focus();
        const len = input.value.length;
        input.setSelectionRange(len, len);
    });
}

function showShellPanel() {
    const shellView = getShellView();
    const empty = getShellEmpty();

    if (shellView) shellView.hidden = false;
    if (empty) empty.hidden = true;
}

function showShellEmpty() {
    const shellView = getShellView();
    const empty = getShellEmpty();

    if (shellView) shellView.hidden = true;
    if (empty) empty.hidden = false;
}

function setShellHeader(agent) {
    const title = getShellTitle();
    const meta = getShellMeta();

    if (title) {
        title.textContent = `Agent ${agent.id} Shell`;
    }

    if (meta) {
        meta.textContent = `${agent.id ?? ""} · ${agent.ip ?? ""} · ${agent.os ?? ""}`;
    }
}

function clearShellTerminal(message = "No shell connected.") {
    const terminal = getShellTerminal();
    if (terminal) terminal.textContent = message;
}

function appendShellOutput(text) {
    const terminal = getShellTerminal();
    if (!terminal) return;

    terminal.textContent += `${terminal.textContent ? "\n" : ""}${String(text ?? "")}`;
    terminal.scrollTop = terminal.scrollHeight;
}

function closeCurrentShell() {
    if (currentShellSession?.socket) {
        try {
            currentShellSession.socket.close();
        } catch (_) {}
    }

    currentShellSession = null;
    currentAgentId = null;
    clearShellTerminal("No shell connected.");
    showShellEmpty();
}

function openShellSocket(wsUrl) {
    const normalized = normalizeWsUrl(wsUrl);
    if (!normalized) {
        appendShellOutput("[error] Missing websocket URL");
        return null;
    }

    const token = localStorage.getItem("access_jwt");
    const csrf_token = localStorage.getItem("csrf-token");
    const socket = new WebSocket(normalized);

    socket.onopen = () => {
        socket.send(JSON.stringify({ type: "auth", access_jwt: token, csrf_token }));
        appendShellOutput("[connected]");
        focusShellInput();
    };

    socket.addEventListener("message", (event) => {
        appendShellOutput(event.data);
    });

    socket.addEventListener("close", () => {
        appendShellOutput("[disconnected]");
    });

    socket.addEventListener("error", () => {
        appendShellOutput("[error]");
    });

    return socket;
}

async function interactAgent(agent) {
    try {
        const response = await fetch(window.get_agent_API, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({ id: agent.id })
        });

        const json = await response.json();

        if (!response.ok || json.result !== "success") {
            throw new Error(json.message || "Failed to get agent websocket route");
        }

        const message = json.message || {};
        const websocketUrl =
            message.websocket_url ||
            message.ws_url ||
            buildAgentWsUrl(agent.id);

        if (currentShellSession?.socket) {
            try {
                currentShellSession.socket.close();
            } catch (_) {}
        }

        currentAgentId = agent.id;
        currentShellSession = {
            agent,
            websocketUrl,
            socket: null
        };

        setShellHeader(agent);
        clearShellTerminal("Connecting...");
        showShellPanel();
        focusShellInput();

        const socket = openShellSocket(websocketUrl);
        currentShellSession.socket = socket;

        resetShellHistoryPointer();
        await loadAgents();
    } catch (error) {
        alert(`Failed to interact with agent: ${error.message}`);
    }
}

async function deleteAgent(agentId) {
    const confirmed = window.confirm(`Delete agent ${agentId}?`);
    if (!confirmed) return;

    try {
        const response = await fetch(window.delete_agent_API, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({ id: agentId })
        });

        const json = await response.json();

        if (!response.ok || json.result !== "success") {
            throw new Error(json.message || "Failed to delete agent");
        }

        if (String(currentAgentId) === String(agentId)) {
            closeCurrentShell();
        }

        await loadAgents();
    } catch (error) {
        alert(`Failed to delete agent: ${error.message}`);
    }
}

function createCell(text) {
    const td = document.createElement("td");
    td.textContent = text ?? "";
    return td;
}

function createActionButton(label, className, datasetKey, datasetValue, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.dataset[datasetKey] = String(datasetValue ?? "");
    button.addEventListener("click", onClick);
    return button;
}

function createAgentRow(agent, allAgents) {
    const tr = document.createElement("tr");

    tr.appendChild(createCell(agent.id));
    tr.appendChild(createCell(agent.ip));
    tr.appendChild(createCell(agent.os));
    tr.appendChild(createCell(formatDate(agent.last_seen)));

    const actionsTd = document.createElement("td");
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "actions";

    const interactBtn = createActionButton(
        "Interact",
        "btn primary",
        "interact",
        agent.id,
        () => {
            const agentId = interactBtn.dataset.interact;
            const selectedAgent = allAgents.find((item) => String(item.id) === String(agentId));
            if (selectedAgent) interactAgent(selectedAgent);
        }
    );

    const deleteBtn = createActionButton(
        "Delete",
        "btn warn",
        "delete",
        agent.id,
        () => {
            deleteAgent(deleteBtn.dataset.delete);
        }
    );

    const fileManagerBtn = createActionButton(
        "File Manager",
        "btn primary",
        "filemanager",
        agent.id,
        () => {
            const agentId = fileManagerBtn.dataset.filemanager;
            window.location = window.filemanager_HTML + "#" + agentId;
            return;
        }
    );

    actionsDiv.appendChild(interactBtn);
    actionsDiv.appendChild(deleteBtn);
    actionsDiv.appendChild(fileManagerBtn);
    actionsTd.appendChild(actionsDiv);
    tr.appendChild(actionsTd);

    return tr;
}

function renderAgentsTable(tbody, agents) {
    tbody.replaceChildren(...agents.map((agent) => createAgentRow(agent, agents)));
}

function renderAgentsError(tbody, message) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");

    td.colSpan = 5;
    td.className = "error";
    td.textContent = `Failed to load agents: ${message}`;

    tr.appendChild(td);
    tbody.replaceChildren(tr);
}

async function loadAgents() {
    if (isLoadingAgents) return;
    isLoadingAgents = true;

    const tbody = document.getElementById("agents-tbody");
    const empty = document.getElementById("agents-empty");

    if (!tbody) {
        isLoadingAgents = false;
        return;
    }

    try {
        const previousAgentIds = new Set(knownAgentIds);

        const response = await fetch(window.list_agents_API, {
            method: "GET",
            credentials: "include",
            headers: {
                "Accept": "application/json"
            }
        });

        const json = await response.json();

        if (!response.ok || json.result !== "success") {
            throw new Error(json.message || "Failed to load agents");
        }

        const agents = Array.isArray(json.message) ? json.message : [];
        agentsCache = agents;

        if (currentAgentId && !agents.some((a) => String(a.id) === String(currentAgentId))) {
            closeCurrentShell();
        }

        if (!agents.length) {
            tbody.replaceChildren();
            knownAgentIds = new Set();
            if (empty) empty.classList.remove("hidden");
            return;
        } else if (empty) {
            empty.classList.add("hidden");
        }

        renderAgentsTable(tbody, agents);

        if (currentShellSession) {
            const updatedAgent = agents.find((a) => String(a.id) === String(currentAgentId));
            if (updatedAgent) {
                currentShellSession.agent = updatedAgent;
                setShellHeader(updatedAgent);
            }
        }

        const currentIds = new Set(agents.map((a) => String(a.id)));
        const newAgents = agents.filter((a) => !previousAgentIds.has(String(a.id)));
        knownAgentIds = currentIds;

        if (
            isAutoInteractEnabled() &&
            newAgents.length > 0 &&
            !currentShellSession
        ) {
            await interactAgent(newAgents[0]);
        }
    } catch (error) {
        renderAgentsError(tbody, error.message);
    } finally {
        isLoadingAgents = false;
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
        loadAgents();
    }, 1000);
}
async function getCurrrentIp() {

    try {
        const response = await fetch(window.get_server_ip_API, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }

        return await response.json();

    } catch (error) {
        console.error("read() error:", error);
        throw error;
    }
}

async function downloadAgent() {
    try {
        const user = getUser();
        const ip = document.getElementById("server-ip-input").value;
        const response = await fetch(window.download_agent_API, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({ user: user.sub,
                ip: ip
             })
        });

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }

    } catch (error) {
        console.error("downloadAgent() error:", error);
        showToast("Download failed");
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    console.log(document.getElementById("download-agent-btn"));
    const resp = await getCurrrentIp();
    document.getElementById("server-ip-input").value = resp.message;
    const downloadBtn = document.getElementById("download-agent-btn");

    if (downloadBtn) {
        downloadBtn.addEventListener("click", downloadAgent);
    }

    const input = getShellInput();
    const endBtn = document.getElementById("end-agent-shell-btn");
    const autoInteractBtn = getAutoInteractButton();



    if (input) {
        input.addEventListener("keydown", (event) => {
            if (event.key === "ArrowUp") {
                event.preventDefault();
                navigateShellHistory("up", input);
                return;
            }

            if (event.key === "ArrowDown") {
                event.preventDefault();
                navigateShellHistory("down", input);
                return;
            }

            if (event.key !== "Enter") return;

            const command = input.value.trim();
            if (!command) return;

            const socket = currentShellSession?.socket;
            if (!socket || socket.readyState !== WebSocket.OPEN) return;

            const escapedCommand = escapeCommand(command);

            socket.send(escapedCommand);
            appendShellOutput(`$ ${escapedCommand}`);
            addToShellHistory(command);
            input.value = "";
            resetShellHistoryPointer();
            focusShellInput();
        });

        input.addEventListener("input", () => {
            resetShellHistoryPointer();
        });
    }

    if (endBtn) {
        endBtn.addEventListener("click", () => {
            closeCurrentShell();
        });
    }

    if (autoInteractBtn) {
        updateAutoInteractButton();
        autoInteractBtn.addEventListener("click", () => {
            setAutoInteractEnabled(!isAutoInteractEnabled());
        });
    }

    showShellEmpty();
    await loadAgents();
    startAutoRefresh();
});