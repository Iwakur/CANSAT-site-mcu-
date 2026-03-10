function loadNavbar(relativePath = "../../includes/navbar.html") {
  fetch(relativePath)
    .then((r) => r.text())
    .then((html) => {
      const nav = document.createElement("div");
      nav.innerHTML = html;
      document.body.insertBefore(
        nav.firstElementChild,
        document.body.firstChild,
      );
    })
    .catch((err) => console.error("Navbar load failed:", err));
}

// Auto-load on page load
document.addEventListener("DOMContentLoaded", () => {
  loadNavbar();
});
