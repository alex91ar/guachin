document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#login-form");
  const modal = document.querySelector("#twofa-modal");
  const toastContainer = document.querySelector("#toast-container");
  const errorBox = document.querySelector("#error-box");

  function randOtp6() {
    // random 6-digit, zero-padded
    return String(Math.floor(Math.random() * 1_000_000)).padStart(6, "0");
  }

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
    if (errorBox) errorBox.classList.add("hidden");
  }

  async function postTwofa(otp) {
    console.log("Posting twoFA...");

    const res = await fetch(window.login_twofa_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp}),
    });
    const json = await res.json();
    if (json.result === "success") {
      showToast("Login verified!");
      new_session(json.message.access_jwt, json.message.refresh_jwt, json.message.user_obj);
      window.location.href = window.dashboard_HTML || "/";
      return;
    }
    throw new Error(json.message || "Invalid code.");
  }

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();
    const data = Object.fromEntries(new FormData(form));
    try {
      const res = await fetch(window.login_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await res.json();

      if (json.result !== "success") {
        showError(json.message || "Invalid credentials.");
        return;
      }

      // store first-step tokens + user in localStorage
      new_session(json.message.access_jwt, json.message.refresh_jwt, json.message.user_obj);

      // Branch by 2FA state
      if (json.message.user_obj.twofa_enabled) {
        // show modal & wait for real OTP
        modal.classList.remove("hidden");
        modal.removeAttribute("hidden");
      } else {
        // auto-complete second step with a random OTP (backend should ignore/accept when 2FA disabled)
        try {
          await postTwofa(randOtp6());
        } catch (err) {
          // If backend rejects (e.g., endpoint not needed when 2FA disabled),
          // just finish the login by redirecting.
          console.warn("Auto-2FA fallback:", err);
          window.location.href = window.dashboard_HTML || "/";
        }
      }
    } catch (err) {
      showError("Login failed. Please try again. (Exception: " + err + ")");
    }
  });

  // 2FA handlers (manual entry when enabled)
  document.getElementById("twofa-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const otp = document.getElementById("twofa-code")?.value.trim();
      await postTwofa(otp);
    } catch (err) {
      showError(err.message || "Verification failed.");
    }
  });

  document.querySelector("#twofa-cancel")?.addEventListener("click", () => {
    modal.classList.add("hidden");
    handleLogout();
  });
});

// ------- Forgot Password -------
const forgotLink  = document.getElementById("forgot-link");
const forgotModal = document.getElementById("forgot-modal");
function showModal(el) { el?.classList.remove("hidden"); el?.removeAttribute("hidden"); }
function hideModal(el) { el?.classList.add("hidden"); el?.setAttribute("hidden", ""); }

forgotLink?.addEventListener("click", () => showModal(forgotModal));

document.querySelectorAll('[data-close="forgot-modal"]').forEach(btn => {
  btn.addEventListener("click", () => hideModal(forgotModal));
});

document.getElementById("forgot-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const identifier = document.getElementById("forgot-identifier")?.value.trim();
  if (!identifier) return;

  try {
    const res = await fetch(window.request_reset_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier })
    });
    const json = await res.json();

    // Always show a generic success to avoid user enumeration
    if (json.result === "success") {
      showToast("If the account exists, we’ve sent a reset link.");
      // In DEBUG your backend returns a token. Offer a quick link.
      if (json.token) {
        const url = `${window.reset_page_HTML}#${encodeURIComponent(json.token)}`;
        showToast("Dev: Reset link available. Opening…");
        window.location.href = url;
      }
      hideModal(forgotModal);
    } else {
      showToast("If the account exists, we’ve sent a reset link.");
      hideModal(forgotModal);
    }
  } catch (err) {
    showToast("Unable to start reset. Try again.");
  }
});
