// ---------- GET 2FA INFO ----------
async function load2fa() {
  const result = await fetch(window.twofa_API);
  let data = await result.json();
  if(data.result === "error" || !result.ok){
    handleLogout();
  }
  else update2FAUI(data.message);
}

document.getElementById("2fa-otp-enable").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    document.getElementById("enable-2fa").click();
  }
});

document.getElementById("2fa-otp-disable").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    document.getElementById("disable-2fa").click();
  }
});

// ---------- ENABLE 2FA ----------
document.getElementById("enable-2fa").addEventListener("click", async () => {
  const otp = document.getElementById("2fa-otp-enable").value.trim();

  if (!otp || !/^\d{6}$/.test(otp)) {
    return showToast("Please enter a valid 6-digit OTP.", "error");
  }

  try {
    const res = await fetch(window.enable_2fa_API, {
      method: "PUT",
      body: JSON.stringify({ otp }),
    });
    let data = await res.json();

    if (data.result !== "success") throw new Error(data.message);
    new_session(data.access_jwt, data.refresh_jwt, data.user_obj);

    showToast("✅ 2FA enabled successfully!", "success");
    await load2fa();
    await loadSessions();
  } catch (err) {
    showToast("❌ Failed to enable 2FA: " + err.message, "error");
  }
});

// ---------- DISABLE 2FA ----------
document.getElementById("disable-2fa").addEventListener("click", async () => {
  const otp = document.getElementById("2fa-otp-disable").value.trim();

  if (!otp || !/^\d{6}$/.test(otp)) {
    return showToast("Please enter a valid 6-digit OTP.", "error");
  }

  try {
    const res = await fetch(window.disable_2fa_API, {
      method: "PUT",
      body: JSON.stringify({ otp }),
    });
    let data = await res.json();

    if (data.result !== "success") throw new Error(data.message);

    showToast("✅ 2FA disabled successfully!", "success");
    await load2fa();
    await loadSessions();
  } catch (err) {
    showToast("❌ Failed to disable 2FA: " + err.message, "error");
  }
});

// ---------- 2FA UI ----------
function update2FAUI(user) {
  const enableUI = document.getElementById("2fa-enable-ui");
  const disableUI = document.getElementById("2fa-disable-ui");
  const enableMsg = document.getElementById("pre-message-enable");
  const disableMsg = document.getElementById("pre-message-disable");
  const qrImg = document.getElementById("2fa-qr");
  const secretEl = document.getElementById("2fa-secret");

  if (user.twofa_enabled) {
    enableUI.classList.add("hidden");
    disableUI.classList.remove("hidden");
    disableMsg.classList.remove("hidden");
    enableMsg.classList.add("hidden");
  } else {
    enableUI.classList.remove("hidden");
    disableUI.classList.add("hidden");
    disableMsg.classList.add("hidden");
    enableMsg.classList.remove("hidden");
    qrImg.src = user.twofa_qr || "";
    secretEl.textContent = user.twofa_secret || "";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // ---------- SHOW / HIDE PASSWORD TOGGLE ----------
document.querySelectorAll(".toggle-password").forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetId = btn.dataset.target;
    const input = document.getElementById(targetId);

    if (!input) return;

    if (input.type === "password") {
      input.type = "text";
      btn.textContent = "🙈";
    } else {
      input.type = "password";
      btn.textContent = "👁";
    }
  });
});

  const openBtn = document.getElementById("open-sessions-modal");
  const modal = document.getElementById("sessions-modal");
  if (openBtn && modal) {
    openBtn.addEventListener("click", async () => {
      await loadSessions();
      modal.classList.remove("hidden");
      modal.hidden = false;
    });

    // click on backdrop closes modal
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.classList.add("hidden");
      }
    });
  }

  // ---------- CHANGE PASSWORD MODAL ----------
  const changePwBtn = document.getElementById("open-change-password-modal");
  const changePwModal = document.getElementById("change-password-modal");
  const changePwForm = document.getElementById("change-password-form");

  if (changePwBtn && changePwModal && changePwForm) {
    // open modal
    changePwBtn.addEventListener("click", () => {
      changePwModal.classList.remove("hidden");
    });

    // buttons with data-close="change-password-modal"
    const closeChangePwButtons = document.querySelectorAll(
      '[data-close="change-password-modal"]'
    );
    closeChangePwButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        changePwModal.classList.add("hidden");
      });
    });

    // click on backdrop closes change-password modal
    changePwModal.addEventListener("click", (e) => {
      if (e.target === changePwModal) {
        changePwModal.classList.add("hidden");
      }
    });

    // submit handler
    changePwForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const oldPassword = document
        .getElementById("old-password")
        .value.trim();
      const newPassword = document
        .getElementById("new-password")
        .value.trim();

      if (!oldPassword || !newPassword) {
        return showToast("Please fill out both password fields.", "error");
      }

      if (newPassword.length < 4) {
        return showToast(
          "New password must be at least 4 characters long.",
          "error"
        );
      }

      try {
        const res = await fetch(window.update_password_API, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            old_password: oldPassword,
            new_password: newPassword,
          }),
        });

        let data = await res.json();

        if (!res.ok || data.result !== "success") {
          throw new Error(data.message || "Password update failed.");
        }

        showToast("✅ Password updated successfully.", "success");
        changePwForm.reset();
        changePwModal.classList.add("hidden");
      } catch (err) {
        showToast("❌ Failed to update password: " + err.message, "error");
      }
    });
  }

  // ESC key closes any open modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (modal && !modal.classList.contains("hidden")) {
        modal.classList.add("hidden");
      }
      if (changePwModal && !changePwModal.classList.contains("hidden")) {
        changePwModal.classList.add("hidden");
      }
    }
  });
});

loadSessions();
load2fa();