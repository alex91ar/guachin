const shellSessions = new Map();
let agentsCache = [];
let refreshTimer = null;
let isLoadingAgents = false;

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
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

function getShellsMenu() {
    return document.getElementById("shells-menu");
}

function getShellsEmpty() {
    return document.getElementById("shells-empty");
}

function getShellViews() {
    return document.getElementById("shell-views");
}

function updateShellsEmptyState() {
    const empty = getShellsEmpty();
    const menu = getShellsMenu();
    if (!empty || !menu) return;

    const hasItems = menu.querySelectorAll(".shell-item").length > 0;
    empty.hidden = hasItems;
}

function setActiveShell(shellKey) {
    document.querySelectorAll(".shell-view").forEach((view) => {
        view.hidden = view.dataset.shellKey !== shellKey;
    });

    document.querySelectorAll(".shell-link").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.shellKey === shellKey);
    });
}

function getCurrentActiveShellKey() {
    return document.querySelector(".shell-link.active")?.dataset.shellKey || null;
}

function appendShellOutput(shellKey, text) {
    const terminal = document.querySelector(`.shell-terminal[data-shell-key="${shellKey}"]`);
    if (!terminal) return;

    terminal.textContent += `${terminal.textContent ? "\n" : ""}${String(text ?? "")}`;
    terminal.scrollTop = terminal.scrollHeight;
}

function closeShell(shellKey) {
    const session = shellSessions.get(shellKey);
    if (session?.socket) {
        try {
            session.socket.close();
        } catch (_) {}
    }

    const view = document.querySelector(`.shell-view[data-shell-key="${shellKey}"]`);
    const menuItem = document.querySelector(`.shell-item[data-shell-key="${shellKey}"]`);

    if (view) view.remove();
    if (menuItem) menuItem.remove();

    shellSessions.delete(shellKey);
    updateShellsEmptyState();

    const firstRemaining = document.querySelector(".shell-link");
    if (firstRemaining) {
        setActiveShell(firstRemaining.dataset.shellKey);
    } else {
        document.querySelectorAll(".shell-view").forEach((remainingView) => {
            remainingView.hidden = true;
        });
    }
}

function removeInvalidShells(validShellKeys) {
    const currentKeys = Array.from(shellSessions.keys());

    currentKeys.forEach((shellKey) => {
        if (!validShellKeys.has(shellKey)) {
            closeShell(shellKey);
        }
    });

    document.querySelectorAll(".shell-item").forEach((item) => {
        const shellKey = item.dataset.shellKey;
        if (!validShellKeys.has(shellKey)) {
            item.remove();
        }
    });

    document.querySelectorAll(".shell-view").forEach((view) => {
        const shellKey = view.dataset.shellKey;
        if (!validShellKeys.has(shellKey)) {
            view.remove();
        }
    });

    updateShellsEmptyState();
}

function createShellMenuItem(shellKey, label, onOpen) {
    const menu = getShellsMenu();
    if (!menu) return;

    let existing = menu.querySelector(`.shell-item[data-shell-key="${shellKey}"]`);
    if (existing) {
        const button = existing.querySelector(".shell-link");
        if (button) button.textContent = String(label ?? "");
        return;
    }

    const item = document.createElement("div");
    item.className = "shell-item";
    item.dataset.shellKey = shellKey;
    item.innerHTML = `
        <button type="button" class="shell-link" data-shell-key="${escapeHtml(shellKey)}">${escapeHtml(label)}</button>
    `;

    item.querySelector(".shell-link").addEventListener("click", async () => {
        await onOpen();
        setActiveShell(shellKey);
    });

    menu.appendChild(item);
    updateShellsEmptyState();
}

function createShellView(shellKey, agent, shell) {
    const container = getShellViews();
    if (!container) return null;

    let view = container.querySelector(`.shell-view[data-shell-key="${shellKey}"]`);
    if (view) {
        const title = view.querySelector(".shell-view-title");
        const meta = view.querySelector(".shell-view-meta");
        if (title) title.textContent = `Shell ${shell.id ?? ""}`;
        if (meta) meta.textContent = `${agent.id ?? ""} · ${agent.ip ?? ""} · ${agent.os ?? ""}`;
        return view;
    }

    view = document.createElement("section");
    view.className = "shell-view";
    view.dataset.shellKey = shellKey;
    view.hidden = true;
    view.innerHTML = `
        <div class="shell-view-header">
            <div>
                <h3 class="shell-view-title">Shell ${escapeHtml(shell.id)}</h3>
                <div class="shell-view-meta">${escapeHtml(agent.id)} · ${escapeHtml(agent.ip)} · ${escapeHtml(agent.os)}</div>
            </div>
            <button type="button" class="btn subtle" data-end-shell>End session</button>
        </div>
        <div class="shell-terminal" data-shell-key="${escapeHtml(shellKey)}">Connecting...</div>
        <div class="shell-input-row">
            <span class="shell-prompt">$</span>
            <input type="text" class="input shell-input" data-shell-input="${escapeHtml(shellKey)}" placeholder="Type a command and press Enter" />
        </div>
    `;

    view.querySelector("[data-end-shell]").addEventListener("click", () => {
        closeShell(shellKey);
        view.hidden = true;
    });

    const input = view.querySelector(`[data-shell-input="${shellKey}"]`);
    input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;

        const command = input.value.trim();
        if (!command) return;

        const session = shellSessions.get(shellKey);
        if (!session?.socket || session.socket.readyState !== WebSocket.OPEN) return;

        session.socket.send(command);
        appendShellOutput(shellKey, `$ ${command}`);
        input.value = "";
    });

    container.appendChild(view);
    return view;
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

function openShellSocket(shellKey, wsUrl) {
    const normalized = normalizeWsUrl(wsUrl);
    if (!normalized) {
        appendShellOutput(shellKey, "[error] Missing websocket URL");
        return null;
    }

    const token = localStorage.getItem("access_jwt");
    const csrf_token = localStorage.getItem("csrf-token");
    const socket = new WebSocket(normalized);

    socket.onopen = () => {
        socket.send(JSON.stringify({ type: "auth", access_jwt: token, csrf_token }));
        appendShellOutput(shellKey, "[connected]");
    };

    socket.addEventListener("message", (event) => {
        appendShellOutput(shellKey, event.data);
    });

    socket.addEventListener("close", () => {
        appendShellOutput(shellKey, "[disconnected]");
    });

    socket.addEventListener("error", () => {
        appendShellOutput(shellKey, "[error]");
    });

    return socket;
}

function ensureShellOpen(agent, shell, websocketUrl, activate = true) {
    const shellKey = `shell-${shell.id}`;

    createShellView(shellKey, agent, shell);

    const existing = shellSessions.get(shellKey);
    if (existing?.socket) {
        existing.agent = agent;
        existing.shell = shell;
        existing.websocketUrl = websocketUrl;
        if (activate) setActiveShell(shellKey);
        return;
    }

    const socket = openShellSocket(shellKey, websocketUrl);
    shellSessions.set(shellKey, {
        agent,
        shell,
        socket,
        websocketUrl
    });

    if (activate) setActiveShell(shellKey);
}

function populateShellMenuFromAgents(agents) {
    const validShellKeys = new Set();
    const activeShellKey = getCurrentActiveShellKey();

    agents.forEach((agent) => {
        const shells = Array.isArray(agent.shells) ? agent.shells : [];

        shells.forEach((shell) => {
            const shellKey = `shell-${shell.id}`;
            validShellKeys.add(shellKey);

            const label = String(shell.id ?? "");
            const websocketUrl = buildAgentWsUrl(shell.id);

            createShellMenuItem(shellKey, label, async () => {
                ensureShellOpen(agent, shell, websocketUrl, true);
            });

            const session = shellSessions.get(shellKey);
            if (session) {
                session.agent = agent;
                session.shell = shell;
                session.websocketUrl = websocketUrl;
            }

            createShellView(shellKey, agent, shell);

            // Auto-connect whenever a shell is available,
            // but do not steal focus from the current active shell.
            ensureShellOpen(agent, shell, websocketUrl, false);
        });
    });

    removeInvalidShells(validShellKeys);

    if (activeShellKey && validShellKeys.has(activeShellKey)) {
        setActiveShell(activeShellKey);
    } else {
        const firstRemaining = document.querySelector(".shell-link");
        if (firstRemaining) {
            setActiveShell(firstRemaining.dataset.shellKey);
        }
    }

    updateShellsEmptyState();
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

        const returnedShell = message.shell ||
            (Array.isArray(agent.shells) && agent.shells.length
                ? agent.shells[agent.shells.length - 1]
                : { id: `temp-${Date.now()}`, agent_id: agent.id });

        const shellKey = `shell-${returnedShell.id}`;
        const label = String(returnedShell.id ?? "");

        createShellMenuItem(shellKey, label, async () => {
            ensureShellOpen(agent, returnedShell, websocketUrl, true);
        });

        ensureShellOpen(agent, returnedShell, websocketUrl, true);

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

        await loadAgents();
    } catch (error) {
        alert(`Failed to delete agent: ${error.message}`);
    }
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

        populateShellMenuFromAgents(agents);

        if (!agents.length) {
            tbody.innerHTML = "";
            if (empty) empty.classList.remove("hidden");
            return;
        } else if (empty) {
            empty.classList.add("hidden");
        }

        tbody.innerHTML = agents.map((agent) => `
            <tr>
                <td>${escapeHtml(agent.id)}</td>
                <td>${escapeHtml(agent.ip)}</td>
                <td>${escapeHtml(agent.os)}</td>
                <td>${escapeHtml(formatDate(agent.last_seen))}</td>
                <td>
                    <div class="actions">
                        <button class="btn primary" data-interact="${escapeHtml(agent.id)}">Interact</button>
                        <button class="btn warn" data-delete="${escapeHtml(agent.id)}">Delete</button>
                    </div>
                </td>
            </tr>
        `).join("");

        tbody.querySelectorAll("[data-interact]").forEach((button) => {
            button.addEventListener("click", () => {
                const agentId = button.dataset.interact;
                const agent = agents.find((item) => String(item.id) === String(agentId));
                if (agent) interactAgent(agent);
            });
        });

        tbody.querySelectorAll("[data-delete]").forEach((button) => {
            button.addEventListener("click", () => {
                deleteAgent(button.dataset.delete);
            });
        });
    } catch (error) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="error">Failed to load agents: ${escapeHtml(error.message)}</td>
            </tr>
        `;
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

document.addEventListener("DOMContentLoaded", async () => {
    await loadAgents();
    startAutoRefresh();
});