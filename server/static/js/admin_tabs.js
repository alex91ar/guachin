// static/js/admin_tabs.js
document.addEventListener("DOMContentLoaded", () => {
  const tabs = Array.from(document.querySelectorAll(".tab"));
  const panels = Array.from(document.querySelectorAll(".tab-panel"));

  function showTab(name) {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    panels.forEach((p) => p.classList.toggle("show", p.id === `tab-${name}`));
  }

  tabs.forEach((btn) => btn.addEventListener("click", () => showTab(btn.dataset.tab)));
});
