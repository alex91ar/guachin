// static/js/passkeys.js

// ---------- NOTIFY HELPERS ----------

function notifyPasskeys(message, type = "info") {
  if (typeof showAlert === "function") return showAlert(message, type);
  if (typeof showToast === "function") return showToast(message, type === "danger" ? "error" : type);
  try {
    alert(message);
  } catch (_) {
    console.log(`[${type}] ${message}`);
  }
}

// ---------- FORMATTERS ----------

function shortId(id) {
  if (!id) return "—";
  const s = String(id);
  return s.length > 16 ? `${s.slice(0, 8)}…${s.slice(-6)}` : s;
}

function fmtB64(b64) {
  if (!b64) return "—";
  const s = String(b64);
  return s.length > 32 ? `${s.slice(0, 16)}…${s.slice(-12)}` : s;
}

// ---------- API ----------

async function apiListPasskeys() {
  const url = window.global_sudo ? window.list_passkeys_SUDO : window.list_passkeys_API;

  const res = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
  const data = await res.json();

  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }
  return data.message || [];
}

async function apiCreatePasskey(payload) {
  const url = window.create_passkey_API;
  if (!url) throw new Error("Missing window.create_passkey_API");

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }
  return data.message || data;
}

async function apiDeletePasskey(payload) {
  const url = window.delete_passkey_SUDO;
  if (!url) throw new Error("Missing window.delete_passkey_API");

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok || data.result !== "success") {
    throw new Error(data.message || `${res.status}`);
  }
  return data.message || data;
}


// ---------- UI WIRING ----------

function setupPasskeysButtons() {
  const refreshBtn = document.getElementById("refresh-passkeys-btn");
  refreshBtn?.addEventListener("click", loadPasskeys);

  // Optional "create" form (only if you add these inputs/buttons to your HTML)
  const createBtn = document.getElementById("create-passkey-btn");
  createBtn?.addEventListener("click", async () => {
    const credentialId = document.getElementById("passkey-credential-id")?.value?.trim();
    const publicKey = document.getElementById("passkey-public-key")?.value?.trim();
    const signCountRaw = document.getElementById("passkey-sign-count")?.value?.trim();

    if (!credentialId || !publicKey) {
      notifyPasskeys("❌ credential_id and public_key are required.", "danger");
      return;
    }

    const signCount = signCountRaw ? Number(signCountRaw) : 0;
    if (!Number.isFinite(signCount) || signCount < 0) {
      notifyPasskeys("❌ sign_count must be a non-negative number.", "danger");
      return;
    }

    try {
      await apiCreatePasskey({
        credential_id: credentialId,
        public_key: publicKey,
        sign_count: signCount,
      });

      notifyPasskeys("✅ Passkey created.", "success");

      // Clear inputs
      const a = document.getElementById("passkey-credential-id");
      const b = document.getElementById("passkey-public-key");
      const c = document.getElementById("passkey-sign-count");
      if (a) a.value = "";
      if (b) b.value = "";
      if (c) c.value = "0";

      await loadPasskeys();
    } catch (err) {
      console.error(err);
      notifyPasskeys(`❌ Failed to create passkey: ${err.message}`, "danger");
    }
  });

  // Optional: submit on Enter inside any "passkey-*" input
  ["passkey-credential-id", "passkey-public-key", "passkey-sign-count"].forEach((id) => {
    const el = document.getElementById(id);
    el?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        createBtn?.click();
      }
    });
  });
}

// ---------- INIT ----------

document.addEventListener("DOMContentLoaded", () => {
  setupPasskeysButtons();
  loadPasskeys();
});
