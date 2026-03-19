function setResult(msg) {
      document.getElementById('result').innerText = msg;
    }

function patchRegistrationOptions(options) {
    // Defensive conversion of keys, and strip out undefined/null fields
    return {
        rp: options.rp,
        user: {
            ...options.user,
            id: base64urlToBuffer(options.user.id),
            displayName: options.user.display_name ?? options.user.displayName ?? "",
            name: options.user.name ?? "",
        },
        challenge: base64urlToBuffer(options.challenge),
        pubKeyCredParams: options.pub_key_cred_params || [],
        timeout: options.timeout,
        excludeCredentials: Array.isArray(options.exclude_credentials)
          ? options.exclude_credentials.map(cred => {
              let patch = { ...cred, id: base64urlToBuffer(cred.id) };
              if (
                  Array.isArray(cred.transports) &&
                  cred.transports.every(t => typeof t === "string")
              ) {
                  patch.transports = cred.transports;
              } else {
                  delete patch.transports;
              }
              return patch;
          })
          : [],
        authenticatorSelection: options.authenticator_selection
          ? {
              authenticatorAttachment: options.authenticator_selection.authenticator_attachment,
              residentKey: options.authenticator_selection.resident_key,
              userVerification: options.authenticator_selection.user_verification,
              requireResidentKey: options.authenticator_selection.require_resident_key
            }
          : undefined,
        attestation: options.attestation,
        extensions: options.extensions
    };
}

function bufferToBase64url(buffer) {
    const bytes = new Uint8Array(buffer);
    let str = '';
    for (let i = 0; i < bytes.length; ++i) str += String.fromCharCode(bytes[i]);
    let b64 = btoa(str)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
    return b64;
}

function prepareRegistrationResponse(credential, username) {
    return {
        username: username,
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        type: credential.type,
        response: {
            clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
            attestationObject: bufferToBase64url(credential.response.attestationObject)
        }
    };
}

// Helper: base64url <-> ArrayBuffer
function base64urlToBuffer(baseurl) {
  // Pad base64url if needed
  let b64 = baseurl.replace(/-/g, '+').replace(/_/g, '/');
  while (b64.length % 4) b64 += '=';
  const str = atob(b64);
  const buf = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i++) buf[i] = str.charCodeAt(i);
  return buf.buffer;
}
    function bufferToBase64url(buffer) {
    const bytes = new Uint8Array(buffer);
    let str = '';
    for (let i = 0; i < bytes.length; ++i) str += String.fromCharCode(bytes[i]);
    let b64 = btoa(str)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
    return b64;
}

async function register_passkey() {
  setResult('');
  // 1. Begin registration
  const beginRes = await fetch(window.register_begin_API, {
    method: 'POST',
    credentials: 'include',
    headers: {
            "Content-Type": "application/json",
        },
    body: JSON.stringify({})
  });
  let options = await beginRes.json();
  options = patchRegistrationOptions(options.public_key);
  // 3. Get credential
  let credential;
  try {
    credential = await navigator.credentials.create({ publicKey: options });
  } catch (e) {
    return setResult('Registration failed: ' + e);
  }
  response = prepareRegistrationResponse(credential, getUser()["sub"]);
  // 4. Send to server
  const completeRes = await fetch(window.passkey_register_complete_API, {
    method: 'POST',
    credentials: 'include',
    headers: {
            "Content-Type": "application/json",
        },
    body: JSON.stringify(response)
  });
  if (completeRes.ok) {
    setResult('Registration successful!');
    fetchPasskeys();
  } else {
    setResult('Registration error: ' + (await completeRes.text()));
  }
}

async function fetchPasskeys() {
  const url = global_sudo ? window.list_passkeys_SUDO : window.list_passkeys_API;
  const resp = await fetch(url, {
    method: "GET",
    credentials: "include",
  });

  if (!resp.ok) {
    setPasskeysResult("Failed to fetch keys.");
    return;
  }
  if (typeof window.loadPasskeys === "function") await loadPasskeys();
  else{
    const data = await resp.json();
    renderPasskeys(data);
  }
}

async function apiDeletePasskey(payload) {
  const url = window.delete_passkey_API;

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

function renderPasskeys(data) {
  const tbody = document.getElementById("passkeys-table")?.querySelector("tbody");
  const twrapper = document.getElementById("passkeys-table-wrapper");
  if (!tbody) return;
  twrapper
  tbody.innerHTML = "";

  const keys = data.message || [];
  if (keys.length === 0) {
    const row = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 3;
    td.textContent = "No passkeys registered.";
    row.appendChild(td);
    tbody.appendChild(row);
    return;
  }

  keys.forEach((k, idx) => {
    const row = document.createElement("tr");

    const tdIdx = document.createElement("td");
    tdIdx.textContent = k.id;
    row.appendChild(tdIdx);

    const tdId = document.createElement("td");
    const codeEl = document.createElement("code");
    const idStr = k.credential_id || "";
    codeEl.textContent = idStr.length > 18 ? `${idStr.slice(0, 10)}...${idStr.slice(-6)}` : idStr;
    tdId.appendChild(codeEl);
    row.appendChild(tdId);

    const tdSign = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn danger";
    delBtn.textContent = "Delete";
    delBtn.addEventListener("click", async () => {
      if (!confirm(`Delete Passkey '${k.id}'?`)) return;

      try {
        // Prefer deleting by id; fall back to repo+tag
        const payload = { id: k.id}

        await apiDeletePasskey(payload);
        fetchPasskeys().catch(() => {});
      } catch (err) {
        console.error(err);
        showToast(`❌ Failed to delete passkey: ${err.message}`, "danger");
      }
    });

    tdSign.textContent = String(k.sign_count ?? 0);
    row.appendChild(tdSign);
    row.appendChild(delBtn);

    tbody.appendChild(row);
  });
}

document.addEventListener("DOMContentLoaded", function () {
  // initial list
  fetchPasskeys().catch(() => {});
  const btn1 = document.getElementById("create-passkey-on-device-btn");
  if (btn1) {
    btn1.addEventListener("click", async () => {
      await register_passkey();
    });
  }
  const btn = document.getElementById("open-passkeys-modal");
  if (btn) {
    btn.addEventListener("click", async () => {
      await fetchPasskeys();
      const modal = document.getElementById("passkeys-modal");
      modal.hidden = false;
      modal.classList.remove("hidden");
    });
  }
});
