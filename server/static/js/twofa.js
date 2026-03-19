document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector(".twofa-input");
  input.focus();

  const form = document.querySelector(".twofa-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    form.classList.add("verifying");
    form.querySelector(".btn").textContent = "Verifying...";
    setTimeout(() => {
      window.location.href = "/"; // redirect to homepage after fake verification
    }, 1500);
  });
});