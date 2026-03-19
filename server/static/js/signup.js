async function signupFlow(ev) {
  ev.preventDefault();
  const form = ev.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());

  if (data.password !== data.confirm_password) {
    showError("Passwords do not match.");
    return;
  }

  try {
    const res = await fetch(window.signup_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: data.id,
        email: data.email,
        password: data.password,
      }),
    });

    const payload = await res.json();

    if (!res.ok || payload.result !== "success") {
      showError(payload.error || "Signup failed. Try again.");
      return;
    }

    // Save JWTs (if returned)
    if (payload.access_jwt) {
      new_session(payload.access_jwt, payload.refresh_jwt);
    }

    // Redirect to profile or dashboard
    window.location.href = "/";
  } catch (err) {
    console.error(err);
    showError("Network error. Please try again.");
  }
}

function showError(msg) {
  const err = document.getElementById("signup-error");
  err.textContent = msg;
  err.style.display = "block";
}

document.getElementById("signup-form")?.addEventListener("submit", signupFlow);
