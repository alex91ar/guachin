document.addEventListener("DOMContentLoaded", () => {
  const transition = document.querySelector(".scroll-transition");
  const featured = document.querySelector(".featured-section");

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          transition.classList.add("visible");
          featured.classList.add("visible");
        }
      });
    },
    { threshold: 0.2 }
  );

  observer.observe(featured);
});