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

function renderPrivileges(privileges) {
    const list = document.getElementById("privileges-list");

    if (!list) return;

    if (!Array.isArray(privileges) || privileges.length === 0) {
        list.innerHTML = `<li class="muted">No privileges found.</li>`;
        return;
    }
    
    list.innerHTML = privileges.map(p => {
        return `
            <li>
                <strong>${escapeHtml(p.name)}</strong> — 
                ${escapeHtml(p.description)} 
                <span class="${p.status === "Enabled" ? "text-success" : "text-muted"}">
                    (${escapeHtml(p.status)})
                </span>
                <td>
                    <button type="button" class="btn btn-sm priv-btn ${p.status === "Enabled" ? "btn-priv" : "btn-danger"}" data-priv="${p.name}" data-enabled="${p.status}">
                        ${p.status === "Enabled" ? "Disable" : "Enable"}
                    </button>
                </td>
            </li>
        `;
    }).join("");
    bindPrivActions();
}

async function getPrivileges(){
    const retmod = await runModule("execkernel \"whoami /priv\"");
    let privileges = [];
    if(retmod.message.retval == 0){
        const to_parse = retmod.message.Output;
        const begin_msg = "State   \r\n========================================= ================================================================== ========\r\n";
        const index = to_parse.indexOf(begin_msg);
        if(index !== -1){
            const result = to_parse.substring(index + begin_msg.length); 
            const array = result.split("\r\n");
            for(const item in array){
                const val = array[item];
                const regex = /^(\S+)\s{2,}(.+?)\s{2,}(Enabled|Disabled).*$/;
                const match = val.match(regex);
                if(match){
                    const privilege = {"name":match[1], "description":match[2], "status":match[3]};
                    privileges.push(privilege);
                }
            }
        }
    }
    return privileges;
}

function formatSize(bytes) {
    if (bytes === null || bytes === undefined || isNaN(bytes)) {
        return "-";
    }

    const numericBytes = Number(bytes);

    if (numericBytes < 1024) {
        return `${numericBytes} bytes`;
    }

    if (numericBytes < 1024 * 1024) {
        return `${(numericBytes / 1024).toFixed(1)} KB`;
    }

    if (numericBytes < 1024 * 1024 * 1024) {
        return `${(numericBytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    return `${(numericBytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function setStatus(message) {
    const statusMessageEl = document.getElementById("status-message");
    if (statusMessageEl) {
        statusMessageEl.textContent = message;
    }
}

function setOutput(message) {
    const outputMessageEl = document.getElementById("output-message");
    if (outputMessageEl) {
        outputMessageEl.textContent = message;
    }
}

function openThreadsModal(title, path, htmlContent) {
    document.getElementById("threads-modal-title").textContent = title || "Threads";
    document.getElementById("threads-modal-path").textContent = path || "";
    document.getElementById("threads-modal-content").innerHTML = htmlContent;
    document.getElementById("threads-modal").classList.remove("hidden");
}

function closeThreadsModal() {
    document.getElementById("threads-modal").classList.add("hidden");
}

function openHandlesModal(title, path, htmlContent) {
    document.getElementById("handles-modal-title").textContent = title || "Handles";
    document.getElementById("handles-modal-path").textContent = path || "";
    document.getElementById("handles-modal-content").innerHTML = htmlContent ?? "";
    document.getElementById("handles-modal").classList.remove("hidden");
}

function closeHandlesModal() {
    document.getElementById("handles-modal").classList.add("hidden");
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

async function ps() {
    return await runModule("ps");
}

async function threads() {
    return await runModule(`threads`);
}

async function handles() {
    return await runModule(`handles`);
}

async function NtQueryObject(type_value, handle) {
    let typeArray = localStorage.getItem("typeCache");
    if(!typeArray){
        localStorage.setItem("typeCache", "[]");
        typeArray = [];
    }
    else{
        typeArray = JSON.parse(typeArray);
        const result = typeArray.find(item => item.type == type_value);
        if(result){
            return result.name;
        }
    }
    const ret_mod = await runModule(`NtQueryObject ${handle} 2`);
    if(ret_mod.message.retval == 0){
        newType = {"type":type_value, "name":ret_mod.message.object_info};
        typeArray.push(newType);
        console.log(typeArray);
        localStorage.setItem("typeCache", JSON.stringify(typeArray));
        return ret_mod.message.object_info;
    }
    else{
        return "Error";
    }
}


async function killProcess(pid) {
    const ntOpenProcessRet = await runModule(`NtOpenProcess 0x${pid.toString(16)} 0x1`);
    if(ntOpenProcessRet.message.retval == 0){
        const ntTerminateProcessRet = await runModule(`NtTerminateProcess ${ntOpenProcessRet.message.handle} 0x0`);
        const ntCloseRet = await runModule(`NtClose ${ntOpenProcessRet.message.handle}`);
    }
}

async function startProcess(command) {
    const imp_token = localStorage.getItem("imp_token");
    if(!imp_token) return await runModule(`execkernel "${String(command).replaceAll('"', '\\"')}"`);
    else return await runModule(`execuser "${String(command).replaceAll('"', '\\"')}" ${imp_token}`);
}

function getMemoryValue(process) {
    return (
        process.private_page_count ??
        process.memory ??
        process.working_set_size ??
        process.virtual_size ??
        null
    );
}

function normalizePidProcessList(data) {
    const message = data?.message;
    if (message && Array.isArray(message.processes)) {
        return message.processes;
    }
    return [];
}

function normalizeThreadsResponse(data, pid) {
    const message = data?.message ?? {};
    const targetPid = Number(pid);

    if (!Array.isArray(message.data)) {
        return [];
    }

    const processEntry = message.data.find((item) => Number(item?.pid) === targetPid);

    if (!processEntry || !Array.isArray(processEntry.threads)) {
        return [];
    }
    return processEntry.threads;
}

function normalizeHandlesResponse(data, pid) {
    const message = data?.message ?? {};
    const targetPid = Number(pid);

    if (!Array.isArray(message.data)) {
        return [];
    }

    const processEntry = message.data.find((item) => Number(item?.pid) === targetPid);
    if (!processEntry || !Array.isArray(processEntry.handles)) {
        return [];
    }
    return processEntry.handles;
}


function parseAccessMask(maskValue, typeName = "") {
    const mask = Number(maskValue);

    if (!Number.isFinite(mask)) {
        return "-";
    }

    const rights = [];

    const add = (flag, label) => {
        if ((mask & flag) === flag) {
            rights.push(label);
        }
    };

    // Standard / generic rights
    add(0x80000000, "GENERIC_READ");
    add(0x40000000, "GENERIC_WRITE");
    add(0x20000000, "GENERIC_EXECUTE");
    add(0x10000000, "GENERIC_ALL");

    add(0x00100000, "SYNCHRONIZE");
    add(0x00080000, "WRITE_OWNER");
    add(0x00040000, "WRITE_DAC");
    add(0x00020000, "READ_CONTROL");
    add(0x00010000, "DELETE");

    const lower = String(typeName || "").toLowerCase();

    if (lower.includes("file")) {
        add(0x0001, "FILE_READ_DATA");
        add(0x0002, "FILE_WRITE_DATA");
        add(0x0004, "FILE_APPEND_DATA");
        add(0x0008, "FILE_READ_EA");
        add(0x0010, "FILE_WRITE_EA");
        add(0x0020, "FILE_EXECUTE");
        add(0x0040, "FILE_DELETE_CHILD");
        add(0x0080, "FILE_READ_ATTRIBUTES");
        add(0x0100, "FILE_WRITE_ATTRIBUTES");
    } else if (lower.includes("process")) {
        add(0x0001, "PROCESS_TERMINATE");
        add(0x0002, "PROCESS_CREATE_THREAD");
        add(0x0008, "PROCESS_VM_OPERATION");
        add(0x0010, "PROCESS_VM_READ");
        add(0x0020, "PROCESS_VM_WRITE");
        add(0x0040, "PROCESS_DUP_HANDLE");
        add(0x0080, "PROCESS_CREATE_PROCESS");
        add(0x0100, "PROCESS_SET_QUOTA");
        add(0x0200, "PROCESS_SET_INFORMATION");
        add(0x0400, "PROCESS_QUERY_INFORMATION");
        add(0x0800, "PROCESS_SUSPEND_RESUME");
        add(0x1000, "PROCESS_QUERY_LIMITED_INFORMATION");
    } else if (lower.includes("thread")) {
        add(0x0001, "THREAD_TERMINATE");
        add(0x0002, "THREAD_SUSPEND_RESUME");
        add(0x0008, "THREAD_GET_CONTEXT");
        add(0x0010, "THREAD_SET_CONTEXT");
        add(0x0020, "THREAD_SET_INFORMATION");
        add(0x0040, "THREAD_QUERY_INFORMATION");
        add(0x0080, "THREAD_SET_THREAD_TOKEN");
        add(0x0100, "THREAD_IMPERSONATE");
        add(0x0200, "THREAD_DIRECT_IMPERSONATION");
        add(0x0400, "THREAD_SET_LIMITED_INFORMATION");
        add(0x0800, "THREAD_QUERY_LIMITED_INFORMATION");
    }

    if (rights.length === 0) {
        return `0x${mask.toString(16).toUpperCase()}`;
    }

    return `${rights.join(" | ")} (0x${mask.toString(16).toUpperCase()})`;
}

async function openProcess(pid){
    const data = await runModule(`OpenProcess ${pid}`);
    const json = data.message.retval;
    if(json == 0) return data.message.handle;
    else return -1;
}

async function duplicateHandle(pid, handle) {
    const processHandle = await openProcess(pid);
    if(processHandle != -1){
        const dupHandle = await runModule(`NtDuplicateObject ${processHandle} ${handle} 0xFFFFFFFFFFFFFFFF 0x1FFFFF 1`);
        if(dupHandle.message.retval == 0){
            return dupHandle.message.new_handle;
        }
    }
}

function renderThreadsTable(threadList, pid) {
    if (!Array.isArray(threadList) || threadList.length === 0) {
        return `<div class="muted">No threads found for PID ${escapeHtml(pid)}.</div>`;
    }

    const rows = threadList.map((thread) => {
        const tid = escapeHtml(thread.tid ?? "-");
        const priority = escapeHtml(thread.priority ?? "-");
        const basePriority = escapeHtml(thread.base_priority ?? "-");
        const state = escapeHtml(thread.thread_state ?? "-");
        const waitReason = escapeHtml(thread.wait_reason ?? "-");
        const startAddress = escapeHtml(
            thread.start_address_hex ??
            (thread.start_address !== undefined && thread.start_address !== null
                ? `0x${Number(thread.start_address).toString(16)}`
                : "-")
        );
        return `
            <tr>
                <td>${tid}</td>
                <td>${priority}</td>
                <td>${basePriority}</td>
                <td>${state}</td>
                <td>${waitReason}</td>
                <td>${startAddress}</td>
                <td>
                    <button type="button" class="btn btn-sm thread-copy-btn" data-tid="${escapeHtml(thread.tid ?? "")}">
                        Copy TID
                    </button>
                </td>
            </tr>
        `;
    }).join("");

    return `
        <table>
            <thead>
                <tr>
                    <th>TID</th>
                    <th>Priority</th>
                    <th>Base Priority</th>
                    <th>State</th>
                    <th>Wait Reason</th>
                    <th>Start Address</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

async function renderHandlesTable(handleList, pid) {
    if (!Array.isArray(handleList) || handleList.length === 0) {
        return `<div class="muted">No handles found for PID ${escapeHtml(pid)}.</div>`;
    }

    const tableId = `handles-table-${pid}-${Date.now()}`;

    const rows = handleList.map((handle, index) => {
        const handleValue =
            handle.handle_value ??
            handle.handle ??
            handle.value ??
            handle.handle_number ??
            "-";

        return `
            <tr data-index="${index}">
                <td>${escapeHtml(handleValue)}</td>
                <td class="handle-type" id="${tableId}-type-${index}">Loading...</td>
                <td id="${tableId}-access-${index}">Loading...</td>
                <td>
                    <button type="button" class="btn btn-sm handle-copy-btn" data-handle="${escapeHtml(handleValue)}">
                        Copy
                    </button>
                </td>
            </tr>
        `;
    }).join("");

    // helper to sort rows by type column
    function sortTable() {
        const tbody = document.querySelector(`#${tableId} tbody`);
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll("tr"));

        rows.sort((a, b) => {
            const aType = a.querySelector(".handle-type")?.textContent || "";
            const bType = b.querySelector(".handle-type")?.textContent || "";
            return aType.localeCompare(bType);
        });

        rows.forEach(row => tbody.appendChild(row));
    }

    setTimeout(async () => {
        for (const [index, handle] of handleList.entries()) {
            const typeCell = document.getElementById(`${tableId}-type-${index}`);
            const accessCell = document.getElementById(`${tableId}-access-${index}`);

            if (!typeCell || !accessCell) continue;

            try {
                const data = await NtQueryObject(handle.type_index, handle.handle);

                const grantedAccess =
                    handle.granted_access ??
                    handle.access_mask ??
                    handle.access ??
                    handle.desired_access;

                const accessText = parseAccessMask(grantedAccess, data);

                typeCell.textContent = data;
                accessCell.textContent = accessText;

                // ✅ re-sort after each update
                sortTable();

            } catch (error) {
                console.error("NtQueryObject error:", error);
                typeCell.textContent = "Error";
                accessCell.textContent = "-";
            }
        }
    }, 0);

    return `
        <table id="${tableId}">
            <thead>
                <tr>
                    <th>Handle</th>
                    <th>Type</th>
                    <th>Access Mask</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

async function adjustPriv(priv, enabled){
    setStatusWindow("", "begin");
    let enable;
    if(enabled == "Enabled") enable = "False";
    else enable = "True";
    setStatusWindow(`Setting privilege ${priv} to ${enable}`, "append");
    const ntopt_ret = await runModule(`NtOpenProcessToken 0xFFFFFFFFFFFFFFFF 0x28`);
    if(ntopt_ret.message.retval == 0){
        setStatusWindow(`NtOpenProcess succeeded NTSTATUS = ${ntopt_ret.message.retval}.`, "append");
        const lookup_ret = await runModule(`LookupPrivilegeValueA ${priv}`);
        if(lookup_ret.message.retval != 0){
            setStatusWindow(`LookupPrivilegeValueA failed. retval = ${lookup_ret.message.retval}.`, "end");
            return {"retval":ntopt_ret.message.retval};
        }
        else{
            setStatusWindow(`LookupPrivilegeValueA succeeded. luid_low = ${lookup_ret.message.luid_low} luid_high = ${lookup_ret.message.luid_high}.`, "append");

            const ntapt_ret = await runModule(`NtAdjustPrivilegesToken ${ntopt_ret.message.h_token} ${lookup_ret.message.luid_low} ${lookup_ret.message.luid_high} ${enable}`);
            if(ntapt_ret.message.retval == 0) setStatusWindow(`NtAdjustPrivilegesToken succeeded. retval = ${ntapt_ret.message.retval}.`, "append");
            else setStatusWindow(`NtAdjustPrivilegesToken failed. retval = ${ntapt_ret.message.retval}.`, "end");
            const ntclose_ret = await runModule(`NtClose ${ntopt_ret.message.h_token}`);
            if(ntclose_ret.message.retval == 0) setStatusWindow(`NtClose succeeded. retval = ${ntclose_ret.message.retval}.`, "end");
            else setStatusWindow(`NtClose failed. retval = ${ntclose_ret.message.retval}.`, "end");
            return {"retval":ntapt_ret.message.retval};
        }
    }
    return {"retval":ntopt_ret.message.retval};
}

function closeActionModal() {
    document.getElementById("process-action-modal").classList.add("hidden");
}

function bindPrivActions() {
    document.querySelectorAll(".priv-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
            document.querySelectorAll(".priv-btn").forEach((button) =>{
                button.disabled=true;
            });
            const priv = event.currentTarget.dataset.priv;
            const enabled = event.currentTarget.dataset.enabled;
            try {
                const ret_ap = await adjustPriv(priv, enabled);
                if(ret_ap.retval == 0) setStatus(`Adjusted privilege ${priv}.`);
                else setStatus(`Error adjusting privilege ${priv} = ${ret_ap.retval}.`);
            } catch (error) {
                setStatus(`Error adjusting privilege.`);
            }
            const data = await getPrivileges();
            renderPrivileges(data);
            document.querySelectorAll(".priv-btn").forEach((button) =>{
                button.disabled=false;
            });
        });
    });
}

function bindThreadModalActions() {
    document.querySelectorAll(".thread-copy-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
            const tid = event.currentTarget.dataset.tid;
            try {
                await copyToClipboard(tid);
                setStatus(`Copied thread id ${tid}.`);
            } catch (error) {
                console.error("Copy TID error:", error);
                setStatus(`Could not copy thread id ${tid}.`);
            }
        });
    });
}

function bindHandleModalActions() {
    document.querySelectorAll(".handle-copy-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
            const handleValue = event.currentTarget.dataset.handle;
            const statusMessageEl = document.getElementById("status-message-handles");
            try {
                const pid = document.querySelector(".process-manager-view-handles-link").dataset.pid;
                console.log(pid);
                const returnval = await duplicateHandle(pid, handleValue);
                
                statusMessageEl.textContent = `New handle ${returnval}.`;
            } catch (error) {
                console.error("Copy handle error:", error);
                statusMessageEl.textContent = `Could not copy handle ${handleValue}.`;
            }
        });
    });
}

async function showThreadsForProcess(proc) {
    try {
        setStatus(`Loading threads for PID ${proc.pid}...`);
        const data = await threads();

        const threadList = normalizeThreadsResponse(data, proc.pid);

        openThreadsModal(
            `Threads - ${proc.name || "Process"}`,
            `PID ${proc.pid}`,
            renderThreadsTable(threadList, proc.pid)
        );

        bindThreadModalActions();
        setStatus(`Loaded ${threadList.length} thread(s) for PID ${proc.pid}.`);
    } catch (error) {
        console.error("Threads load error:", error);
        openThreadsModal(
            `Threads - ${proc.name || "Process"}`,
            `PID ${proc.pid}`,
            `<div class="muted">Could not load threads for PID ${escapeHtml(proc.pid)}.</div>`
        );
        setStatus(`Could not load threads for PID ${proc.pid}.`);
    }
}

async function showHandlesForProcess(proc) {
    try {
        setStatus(`Loading handles for PID ${proc.pid}...`);
        const data = await handles();
        const handleList = normalizeHandlesResponse(data, proc.pid);

        openHandlesModal(
            `Handles - ${proc.name || "Process"}`,
            `PID ${proc.pid}`,
            await renderHandlesTable(handleList, proc.pid)
        );

        bindHandleModalActions();
        setStatus(`Loaded ${handleList.length} handle(s) for PID ${proc.pid}.`);
    } catch (error) {
        console.error("Handles load error:", error);
        openHandlesModal(
            `Handles - ${proc.name || "Process"}`,
            `PID ${proc.pid}`,
            `<div class="muted">Could not load handles for PID ${escapeHtml(proc.pid)}.</div>`
        );
        setStatus(`Could not load handles for PID ${proc.pid}.`);
    }
}

function setStatusWindow(text, startend){
    const statusWindow = document.getElementById("process-action-modal");
    const statusText = document.getElementById("process-action-modal-editor");
    if(startend == "end") {
        statusText.value += "\n";
        statusText.value += text;
        setTimeout(() =>{
            statusWindow.classList.add("hidden");
        }, 5000);

    }
    else if(startend == "begin"){
        statusText.value = "Starting action execution...";
        statusWindow.classList.remove("hidden");
    }
    else if(startend == "append"){
        statusText.value += "\n";
        statusText.value += text;
    }
}

async function impersonateProcess(pid, name){
    setStatusWindow(`Starting impersonation of process ${name} pid = ${pid}.`, "begin");
    const ntOpenProcRet = await runModule(`NtOpenProcess 0x${pid.toString(16)} 0x400`);
    if(ntOpenProcRet.message.retval == 0)
    {
        setStatusWindow(`NtOpenProcess of pid = 0x${pid.toString(16)} desired_access = 0x400 succeded (Handle = ${ntOpenProcRet.message.handle}).`, "append");
        const ntOpenProcTokenRet = await runModule(`NtOpenProcessToken ${ntOpenProcRet.message.handle} 0xa`);
        if(ntOpenProcTokenRet.message.retval == 0){
            setStatusWindow(`NtOpenProcessToken of process handle = ${ntOpenProcRet.message.handle} desired_access = 0xa succeded. (Handle = ${ntOpenProcTokenRet.message.h_token}).`, "append");
            const currentPidRet = await runModule(`GetCurrentProcessId`);
            setStatusWindow(`Current process id = ${currentPidRet.message.pid}`, "append");
            const duplicateTokenExret = await runModule(`DuplicateTokenEx ${ntOpenProcTokenRet.message.h_token} 0x18f 2 2`);
            if(duplicateTokenExret.message.retval == 0){
                setStatusWindow(`DuplicateTokenEx h_token = ${ntOpenProcTokenRet.message.h_token} succeeded. h_new_token = ${duplicateTokenExret.message.h_new_token}.`, "append");
                const ntSetInformationThreadRet = await runModule(`NtSetInformationThread 0xFFFFFFFFFFFFFFFE 5 ${duplicateTokenExret.message.h_new_token}`);
                if(ntSetInformationThreadRet.message.retval == 0){
                    setStatusWindow(`ntSetInformationThreadRet h_token = ${duplicateTokenExret.message.h_new_token} succeeded. NTSTATUS = ${ntSetInformationThreadRet.message.retval}.`, "append");
                    localStorage.setItem("imp_token", duplicateTokenExret.message.h_new_token);
                }
                else{
                    setStatusWindow(`ntSetInformationThreadRet h_token = ${duplicateTokenExret.message.h_new_token} failed. NTSTATUS = ${ntSetInformationThreadRet.message.retval}.`, "append");
                    const ntClose1Ret = await runModule(`NtClose ${duplicateTokenExret.message.h_new_token}`);
                    setStatusWindow(`NtClose of token handle = ${duplicateTokenExret.message.h_new_token} (NTSTATUS = ${ntClose1Ret.message.retval}).`, "append");
                    localStorage.removeItem("imp_token");
                }
                const ntClose2Ret = await runModule(`NtClose ${ntOpenProcRet.message.handle}`);
                setStatusWindow(`NtClose of process handle = ${ntOpenProcRet.message.handle} (NTSTATUS = ${ntClose2Ret.message.retval}).`, "append");
                setStatusWindow(`Finished impersonation.`, "append");
            }
            else{
                setStatusWindow(`DuplicateTokenEx h_token = ${ntOpenProcTokenRet.message.h_token} failed.`, "append");
                const ntCloseRet = await runModule(`NtClose ${ntOpenProcRet.message.handle}`)
                setStatusWindow(`NtClose of process handle = ${ntOpenProcRet.message.handle} (NTSTATUS = ${ntCloseRet.message.retval}).`, "end");
            }
        }
        else{
            setStatusWindow(`NtOpenProcessToken of process handle = ${ntOpenProcRet.message.handle} desired_access = 0xa failed. (NTSTATUS = ${ntOpenProcTokenRet.message.retval}).`, "append");
            const ntCloseRet = await runModule(`NtClose ${ntOpenProcRet.message.handle}`)
            setStatusWindow(`NtClose of process handle = ${ntOpenProcRet.message.handle} (NTSTATUS = ${ntCloseRet.message.retval}).`, "end");
        }
    }
    else{
        setStatusWindow(`NtOpenProcess of pid = 0x${pid.toString(16)} desired_access = 0x400 failed (NTSTATUS = ${ntOpenProcRet.message.retval}).`, "end");
    }
}

async function fillProcessTable() {
    const tableBody = document.getElementById("process-table-body");

    if (!tableBody) {
        console.error("Missing #process-table-body");
        return;
    }

    tableBody.innerHTML = `
        <tr>
            <td colspan="7" class="muted">Loading...</td>
        </tr>
    `;
    setStatus("Loading processes...");

    try {
        const data = await ps();
        const processes = normalizePidProcessList(data).sort((a, b) => {
            const aName = String(a.name ?? "");
            const bName = String(b.name ?? "");
            return aName.localeCompare(bName) || Number(a.pid ?? 0) - Number(b.pid ?? 0);
        });

        if (processes.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="muted">No processes found.</td>
                </tr>
            `;
            setStatus("No processes found.");
            return;
        }

        tableBody.innerHTML = processes.map((proc) => {
            const name = escapeHtml(proc.name ?? "<unknown>");
            const pid = escapeHtml(proc.pid ?? "-");
            const parentPid = escapeHtml(proc.parent_pid ?? "-");
            const threads = escapeHtml(proc.threads ?? "-");
            const handles = escapeHtml(proc.handles ?? "-");
            const memory = escapeHtml(formatSize(getMemoryValue(proc)));

            return `
                <tr>
                    <td>⚙️ ${name}</td>
                    <td>${pid}</td>
                    <td>${parentPid}</td>
                    <td>${threads}</td>
                    <td>${handles}</td>
                    <td>${memory}</td>
                    <td>
                        <div class="file-actions">
                            <a href="#" class="btn-link process-manager-view-threads-link" data-pid="${pid}">Threads</a>
                            <a href="#" class="btn-link process-manager-view-handles-link" data-pid="${pid}">Handles</a>
                            <button type="button" class="btn btn-danger process-manager-impersonate-btn" data-pid="${pid}" data-name="${name}">Impersonate</button>
                            <button type="button" class="btn btn-danger process-manager-kill-btn" data-pid="${pid}">Kill</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");

        tableBody.querySelectorAll(".process-manager-view-threads-link").forEach((link) => {
            link.addEventListener("click", async (event) => {
                event.preventDefault();

                const pid = Number(event.currentTarget.dataset.pid);
                const proc = processes.find((p) => Number(p.pid) === pid);

                if (!proc) {
                    setStatus(`Could not find process ${pid}.`);
                    return;
                }

                await showThreadsForProcess(proc);
            });
        });

        tableBody.querySelectorAll(".process-manager-view-handles-link").forEach((link) => {
            link.addEventListener("click", async (event) => {
                event.preventDefault();

                const pid = Number(event.currentTarget.dataset.pid);
                const proc = processes.find((p) => Number(p.pid) === pid);

                if (!proc) {
                    setStatus(`Could not find process ${pid}.`);
                    return;
                }

                await showHandlesForProcess(proc);
            });
        });

        tableBody.querySelectorAll(".process-manager-impersonate-btn").forEach((button) => {
            button.addEventListener("click", async (event) => {
                event.preventDefault();

                const pid = Number(event.currentTarget.dataset.pid);
                const name = event.currentTarget.dataset.name;

                await impersonateProcess(pid, name);
            });
        });

        tableBody.querySelectorAll(".process-manager-kill-btn").forEach((button) => {
            button.addEventListener("click", async (event) => {
                event.preventDefault();

                const pid = Number(event.currentTarget.dataset.pid);

                try {
                    setStatus(`Killing process ${pid}...`);
                    await killProcess(pid);
                    await fillProcessTable();
                    setStatus(`Process ${pid} terminated.`);
                } catch (error) {
                    console.error("Kill process error:", error);
                    setStatus(`Could not terminate process ${pid}.`);
                }
            });
        });

        setStatus(`Loaded ${processes.length} process(es).`);
    } catch (error) {
        console.error("fillProcessTable error:", error);

        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="muted">Failed to load processes.</td>
            </tr>
        `;
        setStatus("Could not load processes.");
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const data = await getPrivileges();

        renderPrivileges(data);
    } catch (err) {
        console.error("Privileges error:", err);

        const list = document.getElementById("privileges-list");
        if (list) {
            list.innerHTML = `<li class="muted">Could not load privileges.</li>`;
        }
    }
    const agentId = getAgentIdFromHash();
    const currentAgentEl = document.getElementById("current-agent");

    if (currentAgentEl) {
        currentAgentEl.textContent = agentId || "No agent selected";
    }
    document.getElementById("process-action-modal-close").addEventListener("click", closeActionModal);
    document.getElementById("process-action-backdrop").addEventListener("click", closeActionModal);
    document.getElementById("start-process-form").addEventListener("submit", async (event) => {
        event.preventDefault();

        const commandInput = document.querySelector('#start-process-form input[name="command"]');
        const command = commandInput.value.trim();

        if (!command) {
            setStatus("Please enter a command.");
            return;
        }

        try {
            setStatus(`Starting process: ${command}...`);
            const startProcessRet = await startProcess(command);
            setOutput(`Output = ${escapeHtml(startProcessRet.message.Output)}`);
            await fillProcessTable();
            setStatus(`Started process: ${command}...`);
        } catch (error) {
            console.error("Start process error:", error);
            setStatus(`Could not start process: ${command}.`);
        }
    });

    document.getElementById("kill-process-form").addEventListener("submit", async (event) => {
        event.preventDefault();

        const pidInput = document.querySelector('#kill-process-form input[name="pid"]');
        const pid = Number(pidInput.value);

        if (!pid) {
            setStatus("Please enter a valid PID.");
            return;
        }

        try {
            setStatus(`Killing process ${pid}...`);
            await killProcess(pid);
            pidInput.value = "";
            await fillProcessTable();
            setStatus(`Process ${pid} terminated.`);
        } catch (error) {
            console.error("Kill process error:", error);
            setStatus(`Could not terminate process ${pid}.`);
        }
    });

    document.getElementById("threads-modal-close").addEventListener("click", closeThreadsModal);
    document.getElementById("threads-modal-backdrop").addEventListener("click", closeThreadsModal);

    document.getElementById("handles-modal-close").addEventListener("click", closeHandlesModal);
    document.getElementById("handles-modal-backdrop").addEventListener("click", closeHandlesModal);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeThreadsModal();
            closeHandlesModal();
            closeActionModal();
        }
    });

    await fillProcessTable();
});