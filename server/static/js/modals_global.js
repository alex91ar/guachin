// static/js/modals_global.js
(function () {
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

  function getModalRootById(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    return el.classList.contains("modal-overlay") ? el : el.closest(".modal-overlay");
  }

  function topmostOpenModal() {
    const open = Array.from(document.querySelectorAll(".modal-overlay"))
      .filter(m => !m.hasAttribute("hidden"));
    return open.length ? open[open.length - 1] : null;
  }

  function openModal(id) {
    const root = getModalRootById(id);

    if (!root) return;
    root.removeAttribute("hidden");
    

    // bring to front by moving to end of body
    try { document.body.appendChild(root); } catch (_) {}
  }

  function closeModal(id) {
    const root = getModalRootById(id);
    if (!root) return;
    root.setAttribute("hidden", "");
  }

  // expose for your other scripts
  window.openModal = window.openModal || openModal;
  window.closeModal = window.closeModal || closeModal;

  // click handlers: backdrop + [data-close]
  document.addEventListener("click", (e) => {
    const closeBtn = e.target.closest("[data-close]");
    if (closeBtn) {
      const id = closeBtn.getAttribute("data-close");
      if (id) closeModal(id);
      return;
    }
  });

  // ESC closes topmost modal
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const top = topmostOpenModal();
    if (top?.id) closeModal(top.id);
  });

  // ===== Drag =====
  let drag = null;

  document.addEventListener("mousedown", (e) => {
    const handle = e.target.closest("[data-modal-drag-handle]");
    if (!handle) return;

    const root = handle.closest(".modal-overlay");
    if (!root || root.hasAttribute("hidden")) return;

    const win = root.querySelector("[data-modal-window]") || root.querySelector(".modal-window");
    if (!win) return;

    const rect = win.getBoundingClientRect();

    // convert from centered transform to absolute position
    win.style.transform = "none";
    win.style.left = rect.left + "px";
    win.style.top = rect.top + "px";

    drag = {
      win,
      startX: e.clientX,
      startY: e.clientY,
      startLeft: rect.left,
      startTop: rect.top,
    };

    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!drag) return;
    const { win, startX, startY, startLeft, startTop } = drag;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    const newLeft = startLeft + dx;
    const newTop = startTop + dy;

    const maxLeft = window.innerWidth - win.offsetWidth - 8;
    const maxTop = window.innerHeight - win.offsetHeight - 8;

    win.style.left = clamp(newLeft, 8, Math.max(8, maxLeft)) + "px";
    win.style.top = clamp(newTop, 8, Math.max(8, maxTop)) + "px";
  });

  document.addEventListener("mouseup", () => { drag = null; });

  // ===== Resize =====
  let resize = null;

  document.addEventListener("mousedown", (e) => {
    const handle = e.target.closest("[data-modal-resize-handle], .modal-resize-handle");
    if (!handle) return;

    const root = handle.closest(".modal-overlay");
    if (!root || root.hasAttribute("hidden")) return;

    const win = root.querySelector("[data-modal-window]") || root.querySelector(".modal-window");
    if (!win) return;

    const rect = win.getBoundingClientRect();

    // convert to absolute if still centered
    win.style.transform = "none";
    win.style.left = rect.left + "px";
    win.style.top = rect.top + "px";

    resize = {
      win,
      startX: e.clientX,
      startY: e.clientY,
      startW: rect.width,
      startH: rect.height,
    };

    e.preventDefault();
    e.stopPropagation();
  });

  document.addEventListener("mousemove", (e) => {
    if (!resize) return;

    const { win, startX, startY, startW, startH } = resize;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    const minW = 320;
    const minH = 240;

    const maxW = window.innerWidth - (parseFloat(win.style.left || 0) + 8);
    const maxH = window.innerHeight - (parseFloat(win.style.top || 0) + 8);

    win.style.width = clamp(startW + dx, minW, Math.max(minW, maxW)) + "px";
    win.style.height = clamp(startH + dy, minH, Math.max(minH, maxH)) + "px";
  });

  document.addEventListener("mouseup", () => { resize = null; });
})();
