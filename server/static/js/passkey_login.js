function setResult(msg) {
  const el = document.getElementById("result");
  if (el) el.innerText = msg;
}

function base64urlToBuffer(baseurl) {
  let b64 = baseurl.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4) b64 += "=";
  const str = atob(b64);
  const buf = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i++) buf[i] = str.charCodeAt(i);
  return buf.buffer;
}

function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let str = "";
  for (let i = 0; i < bytes.length; ++i) str += String.fromCharCode(bytes[i]);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// ✅ Convert python-fido2 snake_case into WebAuthn camelCase
function patchAuthenticationOptions(pk) {
  const pkey = pk.public_key;
  const allow = Array.isArray(pkey.allow_credentials) ? pkey.allow_credentials : [];
  const extensions = pkey.extensions || undefined;
  return {
    challenge: base64urlToBuffer(pkey.challenge),

    // critical: rpId must be camelCase if present
    rpId: pkey.rp_id || pkey.rpId,

    timeout: pkey.timeout ?? 60000,
    userVerification: pkey.user_verification || pkey.userVerification || "preferred",

    allowCredentials: allow.map((c) => ({
      type: c.type || "public-key",
      id: base64urlToBuffer(c.id),
      // transports optional; keep if array of strings
      ...(Array.isArray(c.transports) ? { transports: c.transports } : {}),
    })),

    ...(extensions ? { extensions } : {}),
  };
}

function prepareAuthenticationResponse(assertion, username) {
  return {
    username,
    id: assertion.id,
    rawId: bufferToBase64url(assertion.rawId),
    type: assertion.type,
    response: {
      clientDataJSON: bufferToBase64url(assertion.response.clientDataJSON),
      authenticatorData: bufferToBase64url(assertion.response.authenticatorData),
      signature: bufferToBase64url(assertion.response.signature),
      userHandle: assertion.response.userHandle
        ? bufferToBase64url(assertion.response.userHandle)
        : null,
    },
  };
}

async function passkeyLogin() {
  setResult("");

  const usernameInput = document.querySelector('input[name="id"]');
  const username = (usernameInput?.value || "").trim();
  if (!username) {
    setResult("Enter your username first to use a passkey.");
    return;
  }

  // 1) Begin
  const beginRes = await fetch(window.passkey_login_begin_API, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  });

  const beginJson = await beginRes.json().catch(() => null);
  if (!beginRes.ok || !beginJson) {
    setResult("Passkey login begin failed.");
    return;
  }
  if (beginJson.result === "error") {
    setResult(beginJson.message || "Passkey login begin error.");
    return;
  }
  new_session(beginJson.message.access_jwt, beginJson.message.refresh_jwt, beginJson.message.user_obj);
  // Your server now returns: { result:"success", public_key: { ... } }
  const publicKey = patchAuthenticationOptions(beginJson.public_key);


  // 2) Get assertion (with an explicit timeout so “hangs” become visible)
  let assertion;
  try {
    const timeoutMs = publicKey.timeout || 60000;

    assertion = await Promise.race([
      navigator.credentials.get({ publicKey }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Timed out waiting for authenticator UI")), timeoutMs + 1500)
      ),
    ]);
  } catch (e) {
    console.error("navigator.credentials.get error:", e);
    setResult("Passkey prompt was cancelled/failed: " + (e?.message || e));
    return;
  }

  // 3) Complete
  const payload = prepareAuthenticationResponse(assertion, username);

  const completeRes = await fetch(window.passkey_login_complete_API, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const completeJson = await completeRes.json().catch(() => null);

  if (completeRes.ok && completeJson?.result === "success") {
    setResult("Passkey login successful!");
    new_session(completeJson.message.access_jwt, completeJson.message.refresh_jwt, completeJson.message.user_obj)
    window.location.href = "/";
  } else {
    setResult(
      "Passkey login error: " +
        (completeJson?.message || (await completeRes.text()))
    );
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("passkey-login-btn");
  if (btn) btn.addEventListener("click", passkeyLogin);
});
