// ---------- CSRF SETUP ----------
if(typeof(meta) === "undefined") window.meta = document.querySelector('meta[name="csrf-token"]');
if (meta) {
  localStorage.setItem("csrf-token", meta.getAttribute("content"));
}

// ✅ Public pages that don’t require authentication
const SAFE_URLS = ["/", "/login", "/signup"];

// ---------- TOAST UTILS ----------
function showToast(message, type = "info") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  toast.addEventListener("click", () => toast.remove());
  container.appendChild(toast);

  setTimeout(() => toast.remove(), 4000);
}

function saveUser(user_obj){
  try{
    const user_string = JSON.stringify(user_obj);
    localStorage.setItem("curr_user", user_string);
  }
  catch(error){
    localStorage.removeItem("curr_user");
    return;
  }
}

function getUser(){
  try{
    const user_obj = JSON.parse(localStorage.getItem("curr_user"));
    return user_obj;
  }
  catch(error){
    return null;
  }
}

// ---------- LINK TOGGLING ----------
function showUserLinks() {
  const curr_user = getUser();
  if(curr_user){
    if(curr_user["roles"].includes("administrator")) { 
      document.getElementById("admin-link").hidden = false;
    }
  }
  else return showGuestLinks();
  document.getElementById("login-link").hidden = true;
  document.getElementById("signup-link").hidden = true;
  document.getElementById("profile-link").hidden = false;
  document.getElementById("agents-link").hidden = false;
  document.getElementById("security-link").hidden = false;
  document.getElementById("logout-link").hidden = false;
}

function showGuestLinks() {
  document.getElementById("login-link").hidden = false;
  document.getElementById("signup-link").hidden = false;
  document.getElementById("security-link").hidden = true;
  document.getElementById("profile-link").hidden = true;
  document.getElementById("agents-link").hidden = true;
  document.getElementById("logout-link").hidden = true;
  document.getElementById("admin-link").hidden = true;
}

async function refreshToken(){
  const refresh_jwt = localStorage.getItem("refresh_jwt");
  const refreshRes = await window._native_fetch(window.refresh_API, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${refresh_jwt}`,
      "X-CSRFToken": localStorage.getItem("csrf-token"),
    },
  });
  return refreshRes;
}

// ---------- LOGOUT ----------
function handleLogout() {
  if(localStorage.getItem("access_jwt")) logoutUser().then(result =>{
      localStorage.clear();
    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
    if (csrf) localStorage.setItem("csrf-token", csrf);
    showUserLinks();
    const path = window.location.pathname;
    if (!SAFE_URLS.includes(path)) {
      window.location.href = "/";
    }
  }).catch(err => {
    showToast("Exception: " + err, "error");
  });
}

async function get_twofa(){
  document.getElementById("twofa-modal").hidden=false;
}

function decodeJwtPayload(token) {
  const payload = token.split('.')[1];

  // fix padding
  const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - base64.length % 4) % 4);

  const decoded = atob(padded);
  return JSON.parse(decoded);
}

function new_session(access_jwt, refresh_jwt, user_object){
  localStorage.setItem("access_jwt", access_jwt);
  localStorage.setItem("refresh_jwt", refresh_jwt);
  let jwt_info = decodeJwtPayload(access_jwt);
  console.log(user_object);
  jwt_info["roles"] = user_object["roles"];
  saveUser(jwt_info);
}

// ---------- FETCH OVERRIDE ----------
if (!window._native_fetch) {
  window._native_fetch = window.fetch;
  window.fetch = async function (url, options = {}) {
    const token = localStorage.getItem("access_jwt");

    const opts = { ...options, headers: { ...(options.headers || {}) } };
    opts.headers["X-CSRFToken"] = localStorage.getItem("csrf-token");
    if (token) opts.headers["Authorization"] = `Bearer ${token}`;
    if (!opts.headers["Content-Type"]) opts.headers["Content-Type"] = "application/json";
    opts.credentials = "include";
    console.log("Calling " + url);
    const response = await window._native_fetch(url, opts);
    const back_response = response.clone();
    const result = await response.json();
    if (result.result === "error") {
      console.log("Error in api call...");
      if (result.message === "access_token_expired") {
        console.log("Token Expired. Refreshing...");
        const refresh = await refreshToken();
        const refreshData = await refresh.json();
        if (refreshData.result === "success") {
          showToast("Refreshed token.")
          new_session(refreshData.access_jwt, refreshData.refresh_jwt, refreshData.user_obj);
          showUserLinks();
          return await window.fetch(url, opts);
        } else {
          handleLogout();
          return refreshData;
        }
      } else if(result.message === "2fa_required") {
      await get_twofa();
      } else if(result.message === "sudo_required") {
      await get_twofa();
      } else if(result.message === "user_not_found") {
      handleLogout();
      return back_response; 
      } else{
        showToast(result.message, "error");
        return back_response;
      }
    }
    return back_response;
  };
}


// ---------- AUTH CHECK ----------
async function checkAuth() {
  const result = await fetch(window.me_API);
  let data = await result.json();
  if(data.result === "error" || !result.ok){
    handleLogout();
  }
  else 
    {
      let jwt_info = decodeJwtPayload(localStorage.getItem("access_jwt"));
      jwt_info["roles"] = data.message["roles"];
      saveUser(jwt_info);
      showUserLinks();
      if (typeof loadUser === "function") loadUser();
    }
}

// ---------- LOGOUT USER ----------
async function logoutUser() {
  const access_jwt = localStorage.getItem("access_jwt");
  const refresh_jwt = localStorage.getItem("refresh_jwt");
  const user_name = getUser().sub;
  try {
    const logoutRes = await fetch(window.logout_API, {
      method: "POST",
      body: JSON.stringify({
        access_jwt,
        refresh_jwt,
        user_name,
      }),
    });
    const logoutData = await logoutRes.json();

    if (logoutData.result === "success") {
      eval(logoutData.message);
    } else {
      showToast(logoutData.message || "Logout failed.", "error");
      localStorage.clear();
    }
  } catch (err) {
    showToast("Logout error: " + err.message, "error");
  }
  finally{
    showUserLinks();
  }
}
