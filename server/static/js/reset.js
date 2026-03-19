document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("reset-form");
  const errorBox = document.getElementById("reset-error-box");
  const toastContainer = document.getElementById("toast-container");
  const tokenInput = document.getElementById("reset-token");

  function showToast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3200);
  }

  function showError(msg) {
    if (errorBox) {
      errorBox.textContent = msg;
      errorBox.classList.remove("hidden");
    } else {
      showToast(msg);
    }
  }

  function hideError() {
    errorBox?.classList.add("hidden");
  }

  function getHashToken() {
    return window.location.hash.replace(/^#/, "").trim();
  }

  tokenInput.value = getHashToken();

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    const token = tokenInput.value;
    const pw1 = document.getElementById("new-password")?.value || "";
    const pw2 = document.getElementById("confirm-password")?.value || "";

    if (!token)
      return showError("Missing or invalid reset token.");

    if (pw1 !== pw2)
      return showError("Passwords do not match.");

    try {
      const res = await fetch(window.confirm_reset_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: pw1 })
      });
      const json = await res.json();

      if (json.result === "success") {
        showToast("Password changed. You can log in now.");
        setTimeout(() => location.href = window.login_page_HTML || "/login", 900);
      } else {
        showError(json.message || "Unable to reset password.");
      }
    } catch (err) {
      showError("Request failed. Please try again.");
    }
  });
});
