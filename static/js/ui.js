// UTF-8
// Global UI helpers — replaces inline on* handlers

document.addEventListener("DOMContentLoaded", () => {
    // Brand logo fallback — replaces onerror="this.style.display='none'"
    const brandLogo = document.querySelector(".brand-logo");
    if (brandLogo) {
        brandLogo.addEventListener("error", () => {
            brandLogo.style.display = 'none';
        });
    }

    // Confirm delete — replaces onsubmit="return confirm(...)"
    document.querySelectorAll("[data-confirm-delete]").forEach(form => {
        form.addEventListener("submit", (e) => {
            const message = form.getAttribute("data-confirm-message") || "Are you sure?";
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
});
