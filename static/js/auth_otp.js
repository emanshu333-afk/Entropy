// BunkLoop OTP via sendotp.email — frontend for /api/auth/* per guide §15
// Link stays same, data via JSON: WSGI sends JSON, JS breaks it down

document.addEventListener("DOMContentLoaded", () => {
    const emailInput = document.querySelector("#id_email");
    const sendBtn = document.querySelector("[data-send-otp]");
    const verifySection = document.querySelector("[data-verify-section]");
    const otpInput = document.querySelector("#id_otp") || document.querySelector("[data-otp-input]");
    const verifyBtn = document.querySelector("[data-verify-otp]");
    const resendBtn = document.querySelector("[data-resend-otp]");
    const statusEl = document.querySelector("[data-otp-status]");
    const universitySelect = document.querySelector("#id_university");

    if (!emailInput) return;

    function setStatus(msg, isError) {
        if (!statusEl) return;
        statusEl.textContent = msg;
        statusEl.style.color = isError ? "#8d2d20" : "var(--muted)";
        statusEl.style.background = isError ? "var(--coral-soft)" : "transparent";
        statusEl.style.padding = msg ? "8px 10px" : "0";
        statusEl.style.borderRadius = msg ? "6px" : "0";
    }

    function getCsrf() {
        return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
    }

    function showProgress() {
        const bar = document.getElementById('progress-bar');
        const overlay = document.getElementById('progress-overlay');
        if (bar) bar.classList.add('is-active');
        if (overlay) { overlay.hidden = false; overlay.classList.add('is-active'); }
        // Also disable main submit to prevent double-click
        const submit = document.querySelector("#signup-submit");
        if (submit) submit.disabled = true;
    }
    function hideProgress() {
        const bar = document.getElementById('progress-bar');
        const overlay = document.getElementById('progress-overlay');
        if (bar) bar.classList.remove('is-active');
        if (overlay) { overlay.classList.remove('is-active'); setTimeout(()=> overlay.hidden = true, 200); }
        const submit = document.querySelector("#signup-submit");
        if (submit) submit.disabled = false;
    }

    async function sendOtp() {
        const email = emailInput.value.trim().toLowerCase();
        if (!email) {
            setStatus("Enter your university email first.", true);
            emailInput.focus();
            return;
        }
        // Basic front-end validation before calling backend (backend will re-validate university domain)
        if (!email.includes("@") || !email.includes(".")) {
            setStatus("Enter a valid email address.", true);
            return;
        }
        setStatus("Sending verification code…");
        showProgress();
        if (sendBtn) sendBtn.disabled = true;
        try {
            const res = await fetch("/api/auth/send-email-otp/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrf(),
                },
                credentials: "same-origin",
                body: JSON.stringify({ email: email }),
            });
            const data = await res.json();
            if (!res.ok) {
                setStatus(data.error || "Could not send OTP.", true);
                if (sendBtn) sendBtn.disabled = false;
                return;
            }
            // Success: WSGI sent JSON {success, message, expires_at, retry_after}
            // JS breaks it down and updates HTML — link stays same
            setStatus(data.message || "Verification code sent. Check your inbox.");
            if (verifySection) verifySection.hidden = false;
            if (otpInput) otpInput.focus();
            // Handle cooldown
            if (data.retry_after) {
                let sec = parseInt(data.retry_after, 10) || 30;
                if (resendBtn) {
                    resendBtn.disabled = true;
                    const orig = resendBtn.textContent;
                    const timer = setInterval(() => {
                        sec--;
                        resendBtn.textContent = `Resend in ${sec}s`;
                        if (sec <= 0) {
                            clearInterval(timer);
                            resendBtn.textContent = orig;
                            resendBtn.disabled = false;
                        }
                    }, 1000);
                }
            }
        } catch (e) {
            setStatus("Network error. Please try again.", true);
        } finally {
            hideProgress();
            if (sendBtn) sendBtn.disabled = false;
        }
    }

    async function verifyOtp(triggerBtn) {
        // Find email and code relative to the clicked verify button if possible (handles multiple OTP inputs on verify page)
        let email = emailInput.value.trim().toLowerCase();
        let code = (otpInput?.value || "").trim();
        // If triggered from a specific button, try to find the closest OTP input
        if (triggerBtn) {
            const container = triggerBtn.closest("div");
            // Look for an input with data-otp-input in the same section or nearby
            const nearbyOtp = container ? container.parentElement?.querySelector("[data-otp-input]") : null;
            // On verify page, the API section has its own input #id_otp_api_verify
            const apiOtp = document.querySelector("#id_otp_api_verify");
            if (apiOtp && apiOtp.value.trim()) {
                code = apiOtp.value.trim();
                // For verify page, email is in hidden #verify-email-hidden or #id_email
                const hiddenEmail = document.querySelector("#verify-email-hidden")?.value || document.querySelector("#id_email")?.value || email;
                if (hiddenEmail) email = hiddenEmail.trim().toLowerCase();
            } else if (nearbyOtp && nearbyOtp.value.trim()) {
                code = nearbyOtp.value.trim();
            }
            // Also check if the trigger is inside a form with its own OTP input
            const formOtp = triggerBtn.closest("form")?.querySelector("[data-otp-input]") || triggerBtn.closest("div")?.querySelector("[data-otp-input]");
            if (formOtp && formOtp.value.trim()) {
                code = formOtp.value.trim();
            }
        }
        if (!email || !code) {
            setStatus("Enter email and 6-digit code.", true);
            return;
        }
        if (!/^\d{6}$/.test(code)) {
            setStatus("Enter a valid 6-digit OTP.", true);
            return;
        }
        setStatus("Verifying…");
        showProgress();
        if (verifyBtn) verifyBtn.disabled = true;
        try {
            const res = await fetch("/api/auth/verify-email-otp/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrf(),
                },
                credentials: "same-origin",
                body: JSON.stringify({ email: email, code: code }),
            });
            const data = await res.json();
            if (!res.ok || !data.verified) {
                setStatus(data.error || "Verification failed.", true);
                if (verifyBtn) verifyBtn.disabled = false;
                hideProgress();
                return;
            }
            // Success: WSGI verified via sendotp.email, set session verified_signup_email
            // JS breaks down JSON {verified:true, message} and updates UI — link stays same
            setStatus(data.message || "Email verified! You can now complete signup.");
            // Mark email as verified in UI
            emailInput.readOnly = true;
            if (universitySelect) universitySelect.disabled = true;
            // Enable the main signup submit if it was disabled pending verification
            const signupSubmit = document.querySelector("#signup-submit") || document.querySelector("button[type=submit]");
            if (signupSubmit) {
                signupSubmit.disabled = false;
                signupSubmit.textContent = "Complete registration";
            }
            // Optionally hide verify section
            // keep it visible for resend, but disable inputs
            if (otpInput) otpInput.disabled = true;
            if (verifyBtn) verifyBtn.disabled = true;
            if (resendBtn) resendBtn.disabled = true;
            hideProgress();
        } catch (e) {
            setStatus("Network error during verification.", true);
            hideProgress();
            if (verifyBtn) verifyBtn.disabled = false;
        }
    }

    // Handle all send/verify buttons (signup and verify pages have multiple)
    document.querySelectorAll("[data-send-otp]").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            sendOtp();
        });
    });
    document.querySelectorAll("[data-verify-otp]").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            verifyOtp(e.currentTarget);
        });
    });
    document.querySelectorAll("[data-resend-otp]").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            sendOtp();
        });
    });

    // If user changes email after verification, require re-verification
    if (emailInput) {
        emailInput.addEventListener("input", () => {
            // Reset verification state if email changes
            if (emailInput.readOnly) {
                emailInput.readOnly = false;
                if (universitySelect) universitySelect.disabled = false;
                if (otpInput) {
                    otpInput.disabled = false;
                    otpInput.value = "";
                }
                if (verifyBtn) verifyBtn.disabled = false;
                if (verifySection) verifySection.hidden = true;
                setStatus("Email changed — please resend code.", true);
            }
        });
    }

    // Progress bar for traditional signup → verify flow (API takes time, show feedback)
    const signupForm = document.querySelector("#signup-form");
    if (signupForm) {
        signupForm.addEventListener("submit", () => {
            // Only show if form is valid (browser will block invalid, but we check)
            if (signupForm.checkValidity()) {
                showProgress();
                // Keep disabled state handled by showProgress
            }
        });
    }
    const verifyForm = document.querySelector("#verify-form-traditional");
    if (verifyForm) {
        verifyForm.addEventListener("submit", () => {
            if (verifyForm.checkValidity()) showProgress();
        });
    }
});
