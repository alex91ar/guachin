

function decodeJwtPayload(token) {
  const payload = token.split(".")[1];
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const decoded = atob(padded);
  return JSON.parse(decoded);
}

function htmlEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

window.loadActions = async function () {
  let data = await fetch(window.list_actions_API);
  data = await data.json();
  const actions = data.message || [];
  window.cachedActions = actions;
  const tbody = document.getElementById("actions-table");
  console.log(tbody);
  tbody.innerHTML = "";
  actions.forEach((a) => {
    const has_priv = getUser().perms.includes(a.id);
    tbody.insertAdjacentHTML(
      "beforeend",
      `
      <tr>
        <td>${a.method}</td>
        <td>${a.path}</td>
        <td>${a.description}</td>
        <td>${has_priv ? "✅" : "❌"}</td>
      </tr>`
    );
  });
};


document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("actions-modal");

  document
    .querySelectorAll('[data-close="actions-modal"]')
    .forEach((btn) => {
      btn.addEventListener("click", () => {
        modal?.classList.add("hidden");
        if (modal) modal.hidden = true;
      });
    });

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.classList.add("hidden");
        modal.hidden = true;
      }
    });
  }
});