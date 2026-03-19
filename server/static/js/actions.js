// static/js/actions.js

(() => {
  // Change this if your backend path is different:
  function setBusy(btn, busy) {
    if (!btn) return;
    btn.disabled = !!busy;
    btn.dataset.prevText ??= btn.textContent;
    btn.textContent = busy ? "⟳ Reloading…" : btn.dataset.prevText;
  }

  async function resetActionsSudo() {
    const btn = document.getElementById("reload-everything-btn");
    if (!btn) return;

    // Optional confirmation (recommended for "reload all" / sudo)
    if (!confirm("Reload ALL actions now?")) return;

    setBusy(btn, true);

    try {
      const res = await fetch(window.reset_actions_SUDO, {
        method: "GET",
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });

      // Try to parse JSON if present
      let data = null;
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("application/json")) data = await res.json();

      if (!res.ok) {
        const msg = (data && (data.error || data.message)) || `${res.status} ${res.statusText}`;
        throw new Error(msg);
      }

      // If you already have a function that reloads actions table, call it:
      // - adjust the function name to whatever you actually use.
      if (typeof window.loadActions === "function") {
        await window.loadActions();
      } else if (typeof window.refreshActions === "function") {
        await window.refreshActions();
      }

    } catch (err) {
      console.error("Failed to reload actions:", err);
      alert(`Failed to reload actions: ${err.message || err}`);
    } finally {
      setBusy(btn, false);
    }
  }

  // Wire up on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("reload-everything-btn");
    if (!btn) return;
    btn.addEventListener("click", resetActionsSudo);
  });
})();

