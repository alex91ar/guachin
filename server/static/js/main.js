document.addEventListener("DOMContentLoaded", () => {
  // Fade-in reveal
  const fadeEls = document.querySelectorAll(".fade-in");
  const observer = new IntersectionObserver(
    (entries) => entries.forEach(e => e.isIntersecting && e.target.classList.add("visible")),
    { threshold: 0.2 }
  );
  fadeEls.forEach(el => observer.observe(el));

  // Burger menu toggle
  const burger = document.getElementById("burger");
  const nav = document.getElementById("site-nav");
  if (burger) {
    burger.addEventListener("click", () => {
      nav.classList.toggle("open");
      burger.classList.toggle("active");
    });
  }
});

window.addEventListener("DOMContentLoaded", () => {
        try { checkAuth(); } catch (_) {}
        try { showUserLinks(); } catch (_) {}

        const burger = document.getElementById("burger");
        const nav = document.getElementById("site-nav");

        burger?.addEventListener("click", () => {
          nav.classList.toggle("open");
          const isOpen = nav.classList.contains("open");
          burger.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", (e) => {
          if (!nav.contains(e.target) && !burger.contains(e.target)) {
            nav.classList.remove("open");
            burger.setAttribute("aria-expanded", "false");
          }
        });

        // Example: show username when logged in
        // Adjust these keys depending on how you store auth/user data
        const usernameDisplay = document.getElementById("username-display");
        const user =
          JSON.parse(localStorage.getItem("user") || "null") ||
          JSON.parse(sessionStorage.getItem("user") || "null");

        if (user && (user.username || user.name)) {
          usernameDisplay.textContent = user.username || user.name;
          usernameDisplay.hidden = false;
        }
      });