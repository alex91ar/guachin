// static/js/images.js

// ---------- NOTIFY HELPERS ----------

function notifyImages(message, type = "info") {
  if (typeof showAlert === "function") return showAlert(message, type);
  if (typeof showToast === "function") return showToast(message, type === "danger" ? "error" : type);
  try {
    // last resort
    alert(message);
  } catch (_) {
    console.log(`[${type}] ${message}`);
  }
}

// ---------- FORMATTERS ----------

function fmtBytes(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n < 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v = v / 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function fmtCreated(created) {
  // supports: unix seconds, unix ms, ISO string
  if (!created) return "—";

  // numeric?
  const num = Number(created);
  if (Number.isFinite(num)) {
    const ms = num > 10_000_000_000 ? num : num * 1000; // if seconds -> ms
    const d = new Date(ms);
    if (!isNaN(d.getTime())) return d.toLocaleString();
  }

  // string ISO?
  const d = new Date(String(created));
  if (!isNaN(d.getTime())) return d.toLocaleString();

  return String(created);
}

function shortImageId(id) {
  if (!id) return "—";
  const s = String(id);
  return s.startsWith("sha256:") ? s.slice(7, 19) : s.slice(0, 12);
}

// ---------- API ----------

async function apiListDockerImages() {
  const url = window.list_docker_images_SUDO;
  if (!url) throw new Error("Missing window.list_docker_images_SUDO");

  const res = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
  let data = await res.json();

  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }

  // Expecting: { result:"success", message:[...] }
  return data.message || [];
}

async function apiDeleteDockerImage(payload) {
  const url = window.remove_docker_image_SUDO;
  if (!url) throw new Error("Missing window.delete_docker_image_SUDO");

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  let data = await res.json();

  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }
  return data.message || data;
}

async function apiPruneDockerImages() {
  const url = window.prune_docker_images_SUDO;
  if (!url) throw new Error("Missing window.prune_docker_images_SUDO");

  const res = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
  let data = await res.json();

  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }
  return data.message || data;
}

// ---------- RENDERING ----------

function renderDockerImages(images) {
  const tbody = document.getElementById("docker-images-tbody");
  const wrapper = document.getElementById("docker-images-table-wrapper");
  const empty = document.getElementById("docker-images-empty");
  if (!tbody) return;

  tbody.innerHTML = "";

  if (!images || images.length === 0) {
    wrapper?.classList.add("hidden");
    empty?.classList.remove("hidden");
    return;
  }

  wrapper?.classList.remove("hidden");
  empty?.classList.add("hidden");

  images.forEach((img) => {
    // Try to support several backend shapes:
    // A) { repository, tag, id, created, size_bytes }
    // B) { name, tag, image_id, created_at, size }
    // C) Docker SDK-like: { RepoTags:[...], Id, Created, Size }
    let repo = img.repository ?? img.repo ?? img.name ?? "—";
    let tag = img.tag ?? "—";

    if (Array.isArray(img.RepoTags) && img.RepoTags.length) {
      // Take the first repotag like "repo:tag"
      const rt = String(img.RepoTags[0] || "");
      const parts = rt.split(":");
      repo = parts[0] || repo;
      tag = parts.slice(1).join(":") || tag;
    }

    const imageId = img.id ?? img.image_id ?? img.Id ?? "";
    const created = img.created ?? img.created_at ?? img.Created ?? "";
    const sizeBytes = img.size_bytes ?? img.size ?? img.Size ?? null;

    const tr = document.createElement("tr");

    const repoTd = document.createElement("td");
    repoTd.textContent = repo;

    const tagTd = document.createElement("td");
    tagTd.textContent = tag;

    const idTd = document.createElement("td");
    idTd.textContent = shortImageId(imageId);

    const createdTd = document.createElement("td");
    createdTd.textContent = fmtCreated(created);

    const sizeTd = document.createElement("td");
    sizeTd.textContent = fmtBytes(sizeBytes);

    const actionsTd = document.createElement("td");
    actionsTd.className = "right";

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn small danger-outline";
    delBtn.textContent = "Delete";
    delBtn.addEventListener("click", async () => {
      const label = `${repo}:${tag}`.replace(":—", "");
      if (!confirm(`Delete docker image '${label}' (${shortImageId(imageId)})?`)) return;

      try {
        // Prefer deleting by id; fall back to repo+tag
        const payload = imageId
          ? { id: imageId }
          : { repository: repo, tag: tag };

        await apiDeleteDockerImage(payload);
        notifyImages("✅ Image deleted.", "success");
        await refreshDockerImages();
      } catch (err) {
        console.error(err);
        notifyImages(`❌ Failed to delete image: ${err.message}`, "danger");
      }
    });

    actionsTd.appendChild(delBtn);

    tr.appendChild(repoTd);
    tr.appendChild(tagTd);
    tr.appendChild(idTd);
    tr.appendChild(createdTd);
    tr.appendChild(sizeTd);
    tr.appendChild(actionsTd);

    tbody.appendChild(tr);
  });
}

// ---------- FLOW ----------

async function refreshDockerImages() {
  try {
    const images = await apiListDockerImages();
    renderDockerImages(images);
  } catch (err) {
    console.error("Failed to load docker images:", err);
    notifyImages(`❌ Failed to load docker images: ${err.message}`, "danger");
    renderDockerImages([]);
  }
}

// ---------- UI WIRING ----------

function setupDockerImagesButtons() {
  const refreshBtn = document.getElementById("refresh-images-btn");
  refreshBtn?.addEventListener("click", refreshDockerImages);

  const pruneBtn = document.getElementById("prune-images-btn");

  pruneBtn?.addEventListener("click", async () => {
    if (!confirm("Prune unused docker images? This can remove dangling/unused layers.")) return;

    try {
      const result = await apiPruneDockerImages();
      notifyImages("✅ Images pruned.", "success");
      await refreshDockerImages();
    } catch (err) {
      console.error(err);
      notifyImages(`❌ Failed to prune images: ${err.message}`, "danger");
    }
  });
}

// ---------- INIT ----------

document.addEventListener("DOMContentLoaded", () => {
  setupDockerImagesButtons();

  // Load once at startup (optional). If you want only on tab open, tell me and I’ll hook into your tab switcher.
  refreshDockerImages();
});

document.getElementById("prune-temp-containers-btn")?.addEventListener("click", async () => {
  if (!confirm("Prune temporary Docker images? This cannot be undone.")) return;

  try {
    const res = await fetch(window.prune_temp_images_SUDO, {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });

    if (!res.ok) throw new Error("Failed to prune temp images");

    alert("Temporary images pruned successfully.");
    refreshDockerImages();
  } catch (err) {
    console.error(err);
    alert("Error pruning temporary images.");
  }
});
