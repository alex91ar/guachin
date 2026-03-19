(function () {
  // Sidebar toggle (mobile)
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebarToggle");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("is-open");
    });
  }

  // Tabs
  document.querySelectorAll("[data-tabs]").forEach((tabs) => {
    const bar = tabs.querySelector(".tabs__bar");
    const panes = tabs.querySelectorAll(".tabs__pane");
    if (!bar) return;

    bar.addEventListener("click", (e) => {
      const btn = e.target.closest(".tabs__btn");
      if (!btn) return;
      const id = btn.dataset.tab;
      bar.querySelectorAll(".tabs__btn").forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      panes.forEach(p => p.classList.toggle("is-active", p.id === `tab-${id}`));
    });
  });

  // Modals
  document.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-open");
      const modal = document.getElementById(id);
      if (modal) modal.setAttribute("aria-hidden", "false");
    });
  });
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const modal = btn.closest(".modal");
      if (modal) modal.setAttribute("aria-hidden", "true");
    });
  });
  document.querySelectorAll(".modal").forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) m.setAttribute("aria-hidden", "true");
    });
  });
})();
