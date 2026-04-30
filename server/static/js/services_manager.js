function getAgentIdFromHash() {
    const hash = window.location.hash || "";
    return hash.startsWith("#") ? hash.slice(1) : hash;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function setStatus(message) {
    const statusMessageEl = document.getElementById("status-message");
    if (statusMessageEl) {
        statusMessageEl.textContent = message;
    }
}

function setStatusWindow(text, startend) {
    const statusWindow = document.getElementById("service-action-modal");
    const statusText = document.getElementById("service-action-modal-editor");

    if (!statusWindow || !statusText) return;

    if (startend === "begin") {
        statusText.value = text || "Starting service action...";
        statusWindow.classList.remove("hidden");
    } else if (startend === "append") {
        statusText.value += "\n" + text;
    } else if (startend === "end") {
        statusText.value += "\n" + text;

        setTimeout(() => {
            statusWindow.classList.add("hidden");
        }, 5000);
    }

    statusText.selectionStart = statusText.selectionEnd = statusText.value.length;
    statusText.scrollTop = statusText.scrollHeight;
}

function closeActionModal() {
    document.getElementById("service-action-modal").classList.add("hidden");
}

function closeQueryModal() {
    document.getElementById("service-query-modal").classList.add("hidden");
}

async function runModule(moduleName) {
    const agentId = getAgentIdFromHash();

    const response = await fetch(window.run_module_API, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            agent_id: agentId,
            module: moduleName
        })
    });

    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }

    return await response.json();
}

async function getServices() {
    return await runModule("services");
}


async function startService(serviceName) {
    setStatusWindow(`Starting service ${serviceName}`, "begin");
    const scManager = await runModule(`OpenSCManagerW "" "" 0xF003F`);
    if(scManager.message.retval == 0){
        setStatusWindow(`Success opening SCManager handle = ${scManager.message.handle}`, "append");
        const openService = await runModule(`OpenServiceW ${scManager.message.handle} ${serviceName} 0xF01FF`);
        if(openService.message.retval == 0){
            setStatusWindow(`Success opening service = ${openService.message.h_service}`, "append");
            const startService = await runModule(`StartServiceA ${openService.message.h_service}`, "append");
            if(startService.message.retval == 0){
                setStatusWindow(`Success starting service`, "append");
            }
            else{
                setStatusWindow(`Failure starting service`, "append");
            }
            const endService = await runModule(`CloseServiceHandle ${openService.message.h_service}`);
        }
        else{
            setStatusWindow(`Failure opening service = ${openService.message.h_service}`, "append");
        }
        const closeSCM = await runModule(`CloseServiceHandle ${scManager.message.handle}`)
    }
    else{
        setStatusWindow(`Error opening SCManager`, "end");
    }
}

async function stopService(serviceName) {
    setStatusWindow(`Stopping service ${serviceName}`, "begin");
    const scManager = await runModule(`OpenSCManagerW "" "" 0xF003F`);
    if(scManager.message.retval == 0){
        setStatusWindow(`Success opening SCManager handle = ${scManager.message.handle}`, "append");
        const openService = await runModule(`OpenServiceW ${scManager.message.handle} ${serviceName} 0xF01FF`);
        if(openService.message.retval == 0){
            setStatusWindow(`Success opening service = ${openService.message.h_service}`, "append");
            const startService = await runModule(`ControlService ${openService.message.h_service} 1`, "append");
            if(startService.message.retval == 0){
                setStatusWindow(`Success stopping service`, "append");
            }
            else{
                setStatusWindow(`Failure stopping service`, "append");
            }
            const endService = await runModule(`CloseServiceHandle ${openService.message.h_service}`);
        }
        else{
            setStatusWindow(`Failure opening service = ${openService.message.h_service}`, "append");
        }
        const closeSCM = await runModule(`CloseServiceHandle ${scManager.message.handle}`)
    }
    else{
        setStatusWindow(`Error opening SCManager`, "end");
    }
}

function renderStartTypeSelect(currentStartType) {
    const options = [
        { value: 2, label: "Automatic" },
        { value: 3, label: "Manual" },
        { value: 4, label: "Disabled" }
    ];

    // normalize input (can be number or string)
    const normalized = String(currentStartType).toLowerCase();

    return `
        <select class="start-type-select" id="start-type-select">
            ${options.map(opt => {
                const isSelected =
                    normalized == String(opt.value) ||
                    normalized === opt.label.toLowerCase();

                return `
                    <option value="${opt.value}" ${isSelected ? "selected" : ""}>
                        ${opt.label}
                    </option>
                `;
            }).join("")}
        </select>
    `;
}

function renderServiceTypeSelect(currentServiceType) {
    const options = [
        { value: 0x10, label: "Win32 Own Process" },
        { value: 0x20, label: "Win32 Share Process" },
        { value: 0x110, label: "Own Process (Interactive)" },
        { value: 0x120, label: "Share Process (Interactive)" },
        { value: 0x1, label: "Kernel Driver" },
        { value: 0x2, label: "File System Driver" }
    ];

    const normalized = Number(currentServiceType);

    return `
        <select class="service-type-select" id="service-type-select">
            ${options.map(opt => {
                const isSelected = normalized === opt.value;

                return `
                    <option value="${opt.value}" ${isSelected ? "selected" : ""}>
                        ${opt.label} (0x${opt.value.toString(16)})
                    </option>
                `;
            }).join("")}
        </select>
    `;
}

async function queryService(serviceName) {
    const statusWindow = document.getElementById("service-query-modal").classList.remove("hidden");
    const queryServiceWindow = document.getElementById("service-query-modal-editor");
    queryServiceWindow.innerHTML = `Loading service ${serviceName} info`;
    const scManager = await runModule(`OpenSCManagerW "" "" 0xF003F`);
    if(scManager.message.retval == 0){
        queryServiceWindow.innerHTML += `<br>Success opening SCManager handle = ${scManager.message.handle}`;
        const openService = await runModule(`OpenServiceW ${scManager.message.handle} ${serviceName} 0xF01FF`);
        if(openService.message.retval == 0){
            queryServiceWindow.innerHTML += `<br>Success opening service = ${openService.message.h_service}`;
            const queryService = await runModule(`QueryServiceConfigW ${openService.message.h_service} 0x2000`);
            if(queryService.message.retval == 0){
                queryServiceWindow.innerHTML += `<br>Success querying service`;
                queryServiceWindow.innerHTML += `<br>Path: <input type="text" value="${escapeHtml(queryService.message.binary_path)}" size=50>`;
                queryServiceWindow.innerHTML += `<br>User: <input type="text" value="${escapeHtml(queryService.message.account_name)}" size=50>`;
                queryServiceWindow.innerHTML += `<br><label for="start-type-select">Start Type ${renderStartTypeSelect(queryService.message.start_type)}</label>     `;
                queryServiceWindow.innerHTML += `<br><label for="service-type-select">Service Type ${renderServiceTypeSelect(queryService.message.service_type)}</label> `;
            }
            else{
                queryServiceWindow.value += `\nFailure querying service`;
            }
            const endService = await runModule(`CloseServiceHandle ${openService.message.h_service}`);
        }
        else{
            queryServiceWindow.value += `\nFailure opening service = ${openService.message.h_service}`;
        }
        const closeSCM = await runModule(`CloseServiceHandle ${scManager.message.handle}`)
    }
    else{
        queryServiceWindow.value += `\nError opening SCManager`;
    }
}

function getServiceStatus(service) {
    return (
        service.status ??
        service.state ??
        service.current_state ??
        service.service_state ??
        "-"
    );
}

function getServiceStartType(service) {
    return (
        service.start_type ??
        service.startType ??
        service.start_mode ??
        service.startMode ??
        "-"
    );
}

function getServicePid(service) {
    return (
        service.pid ??
        service.process_id ??
        service.processId ??
        "-"
    );
}

function getServiceBinaryPath(service) {
    return (
        service.binary_path ??
        service.binaryPath ??
        service.path ??
        service.image_path ??
        service.imagePath ??
        "-"
    );
}

function renderStatusBadge(status) {
    const normalized = String(status || "").toLowerCase();

    if (normalized.includes("running")) {
        return `<span class="text-success">${escapeHtml(status)}</span>`;
    }

    if (normalized.includes("stopped")) {
        return `<span class="text-muted">${escapeHtml(status)}</span>`;
    }

    return escapeHtml(status);
}

function normalizeServicesResponse(data) {
    const message = data?.message;

    if (Array.isArray(message?.ret_struct)) {
        return message.ret_struct;
    }

    if (Array.isArray(message?.services)) {
        return message.services;
    }

    if (Array.isArray(message?.data)) {
        return message.data;
    }

    return [];
}

async function fillServicesTable() {
    const tableBody = document.getElementById("services-table-body");

    if (!tableBody) {
        console.error("Missing #services-table-body");
        return;
    }

    tableBody.innerHTML = `
        <tr>
            <td colspan="6" class="muted">Loading...</td>
        </tr>
    `;

    setStatus("Loading services...");

    try {
        const data = await getServices();

        const services = normalizeServicesResponse(data).sort((a, b) => {
            const aName = String(a.service_name || a.name || a.display_name || "");
            const bName = String(b.service_name || b.name || b.display_name || "");
            return aName.localeCompare(bName);
        });

        if (services.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="muted">No services found.</td>
                </tr>
            `;
            setStatus("No services found.");
            return;
        }

        tableBody.innerHTML = services.map((service) => {
            const rawName = service.service_name || service.name || "";
            const rawDisplayName = service.display_name || service.displayName || rawName || "-";

            const name = escapeHtml(rawName || "-");
            const displayName = escapeHtml(rawDisplayName);
            const status = service.status || `State ${service.state ?? "-"}`;
            const pid = escapeHtml(service.pid ?? "-");
            const serviceType = escapeHtml(service.service_type ?? "-");
            const win32ExitCode = escapeHtml(service.win32_exit_code ?? "-");

            return `
                <tr>
                    <td>🧩 ${name}</td>
                    <td>${displayName}</td>
                    <td>${renderStatusBadge(status)}</td>
                    <td>${pid}</td>
                    <td>${serviceType}</td>
                    <td>${win32ExitCode}</td>
                    <td>
                        <div class="file-actions">
                            <button type="button" class="btn btn-priv service-start-btn" data-service="${escapeHtml(rawName)}" ${!rawName ? "disabled" : ""}>
                                Start
                            </button>
                            <button type="button" class="btn btn-danger service-stop-btn" data-service="${escapeHtml(rawName)}" ${!rawName ? "disabled" : ""}>
                                Stop
                            </button>
                            <button type="button" class="btn btn-sm service-query-btn" data-service="${escapeHtml(rawName)}" ${!rawName ? "disabled" : ""}>
                                Query
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");

        bindServiceActions();
        setStatus(`Loaded ${services.length} service(s).`);
    } catch (error) {
        console.error("fillServicesTable error:", error);

        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="muted">Failed to load services.</td>
            </tr>
        `;

        setStatus("Could not load services.");
    }
}

function bindServiceActions() {
    document.querySelectorAll(".service-start-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();

            const serviceName = event.currentTarget.dataset.service;

            try {
                document.querySelectorAll(".service-start-btn, .service-stop-btn, .service-query-btn")
                    .forEach((btn) => btn.disabled = true);

                setStatusWindow(`Starting service ${serviceName}...`, "begin");

                await startService(serviceName);

                await fillServicesTable();
                setStatus(`Started service ${serviceName}.`);
            } catch (error) {
                console.error("Start service error:", error);
            } finally {
                document.querySelectorAll(".service-start-btn, .service-stop-btn, .service-query-btn")
                    .forEach((btn) => btn.disabled = false);
            }
        });
    });

    document.querySelectorAll(".service-stop-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();

            const serviceName = event.currentTarget.dataset.service;

            try {
                document.querySelectorAll(".service-start-btn, .service-stop-btn, .service-query-btn")
                    .forEach((btn) => btn.disabled = true);

                setStatusWindow(`Stopping service ${serviceName}...`, "begin");

                await stopService(serviceName);

                await fillServicesTable();
                setStatus(`Stopped service ${serviceName}.`);
            } catch (error) {
                console.error("Stop service error:", error);
            } finally {
                document.querySelectorAll(".service-start-btn, .service-stop-btn, .service-query-btn")
                    .forEach((btn) => btn.disabled = false);
            }
        });
    });

    document.querySelectorAll(".service-query-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();

            const serviceName = event.currentTarget.dataset.service;

            try {
                await queryService(serviceName);
            } catch (error) {
                console.error("Query service error:", error);
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const agentId = getAgentIdFromHash();
    const currentAgentEl = document.getElementById("current-agent");

    if (currentAgentEl) {
        currentAgentEl.textContent = agentId || "No agent selected";
    }

    document.getElementById("service-action-modal-close")
        .addEventListener("click", closeActionModal);

    document.getElementById("service-action-backdrop")
        .addEventListener("click", closeActionModal);

    document.getElementById("service-query-modal-close")
        .addEventListener("click", closeQueryModal);

    document.getElementById("service-query-backdrop")
        .addEventListener("click", closeQueryModal);

    document.getElementById("refresh-services-btn")
        .addEventListener("click", async (event) => {
            event.preventDefault();
            event.currentTarget.disabled = true;
            await fillServicesTable();
            event.currentTarget.disabled = false;
        });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeActionModal();
            closeQueryModal();
        }
    });

    await fillServicesTable();
});