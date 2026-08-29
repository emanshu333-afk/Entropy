// UTF-8 — home.js — for home.html
// Handles browse toolbar: keeps link same, JS fetches filtered results via JSON if needed
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector(".browse-toolbar");
    // The form already does GET, but JS can enhance to fetch without full reload
    // For now, just ensure UTF-8 handling and that the page is correctly encoded
    if (form) {
        form.setAttribute("accept-charset", "UTF-8");
    }
});
