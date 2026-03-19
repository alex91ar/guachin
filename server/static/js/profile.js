// ---------- MAIN LOGIC ----------
const token = localStorage.getItem("access_jwt");
if (!token) window.location.href = "/login";

const statusEl = document.getElementById("profile-status");
const form = document.getElementById("profile-form");
const legalContainer = document.getElementById("legal-fields");

const API = {
  details: window.update_details_API,
  enable2fa: window.enable_2fa_API,
  disable2fa: window.disable_2fa_API,
};

// ---------- LOAD USER FROM LOCALSTORAGE ----------
function loadUser() {
  const stored = getUser();
  
  if (!stored) {
    statusEl.textContent = "No user data found — please refresh or log in again.";
    form.classList.add("hidden");
    return;
  }

  statusEl.classList.add("hidden");
  form.classList.remove("hidden");

  document.getElementById("profile-name").value = stored.id || "";
  document.getElementById("profile-email").value = stored.email || "";
  document.getElementById("profile-description").value = stored.description || "";

  // Populate legal fields
  legalContainer.innerHTML = "";
  Object.entries(stored)
    .filter(([key]) => key.startsWith("legal_"))
    .forEach(([key, val]) => {
      const label = document.createElement("label");
      label.innerHTML = `
        <span>${key.replace("legal_", "").replace(/_/g, " ").toUpperCase()}</span>
        <input type="text" name="${key}" value="${val || ""}">
      `;
      legalContainer.appendChild(label);
    });
}

// ---------- SAVE PROFILE ----------
document.getElementById("save-profile").addEventListener("click", async () => {
  const email = document.getElementById("profile-email").value;
  const description = document.getElementById("profile-description").value;


  try {
    await fetch(API.details, {
      method: "PUT",
      body: JSON.stringify({ email, description }),
    });


    showToast("✅ Profile updated successfully!", "success");
    await checkAuth();
    loadUser();
  } catch (err) {
    showToast("❌ Failed to save profile: " + err.message, "error");
  }
});

document.getElementById("profile-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    document.getElementById("save-profile").click();
  }
});

document.getElementById("profile-email").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    document.getElementById("save-profile").click();
  }
});

document.getElementById("profile-description").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    document.getElementById("save-profile").click();
  }
});

loadUser();