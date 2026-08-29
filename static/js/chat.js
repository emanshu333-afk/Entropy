// BunkLoop real-time chat — plan §15,42,43
document.addEventListener("DOMContentLoaded", () => {
    const chatContainer = document.querySelector("[data-chat-container]");
    const messagesEl = document.querySelector("[data-messages]");
    const form = document.querySelector("[data-chat-form]");
    const input = document.querySelector("[data-chat-input]");
    const statusEl = document.querySelector("[data-chat-status]");

    if (!chatContainer || !form || !input) return;

    const conversationId = chatContainer.dataset.conversationId;
    const conversationUuid = chatContainer.dataset.conversationUuid;
    // Use UUID if available, else pk (plan prefers UUID)
    const wsId = conversationUuid && conversationUuid !== "None" && conversationUuid !== "" ? conversationUuid : conversationId;
    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${wsScheme}://${window.location.host}/ws/chat/${wsId}/`;

    let socket = null;
    let reconnectAttempts = 0;
    const maxBackoff = 16000;

    function setStatus(text, isError) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.style.color = isError ? "#8d2d20" : "var(--muted)";
    }

    function scrollToBottom() {
        if (messagesEl) {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
    }

    function appendMessage(msg, isOwn) {
        if (!messagesEl) return;
        // Remove empty state if present
        const empty = messagesEl.querySelector("[data-empty]");
        if (empty) empty.remove();

        const row = document.createElement("div");
        row.style.display = "flex";
        row.style.justifyContent = isOwn ? "flex-end" : "flex-start";

        const bubble = document.createElement("div");
        bubble.style.maxWidth = "72%";
        bubble.style.padding = "10px 14px";
        bubble.style.borderRadius = "14px";
        bubble.style.fontSize = "14px";
        bubble.style.lineHeight = "1.4";
        if (isOwn) {
            bubble.style.background = "var(--coral)";
            bubble.style.color = "#fff";
            bubble.style.borderBottomRightRadius = "4px";
        } else {
            bubble.style.background = "#fff";
            bubble.style.border = "1px solid var(--line)";
            bubble.style.borderBottomLeftRadius = "4px";
        }

        const text = document.createElement("div");
        text.textContent = msg.content || msg.body || "";
        // Simple line breaks
        text.innerHTML = (msg.content || msg.body || "").replace(/\n/g, "<br>");
        bubble.appendChild(text);

        const meta = document.createElement("div");
        meta.style.fontSize = "10px";
        meta.style.marginTop = "6px";
        meta.style.opacity = "0.75";
        const senderName = msg.sender_name || msg.sender?.name || (isOwn ? "You" : "Seller");
        const createdAt = msg.created_at ? new Date(msg.created_at).toLocaleString() : new Date().toLocaleString();
        meta.textContent = `${senderName} · ${createdAt}`;
        bubble.appendChild(meta);

        row.appendChild(bubble);
        messagesEl.appendChild(row);
        scrollToBottom();
    }

    function connect() {
        setStatus("Connecting…");
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            setStatus("Connected — real-time");
            reconnectAttempts = 0;
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === "message.new" && data.message) {
                    const msg = data.message;
                    // Deduplicate by id if already in DOM (plan §44)
                    if (document.querySelector(`[data-message-id="${msg.id}"]`)) return;
                    const isOwn = msg.sender_id === parseInt(chatContainer.dataset.currentUserId, 10) || msg.sender_registration_id === chatContainer.dataset.currentRegistrationId;
                    appendMessage(msg, isOwn);
                } else if (data.type === "message.read") {
                    // Could show read receipt
                    setStatus(`Read by ${data.user_id}`);
                } else if (data.type === "typing.start" || data.type === "typing.stop") {
                    setStatus(data.type === "typing.start" ? `${data.username} is typing…` : "Connected — real-time");
                } else if (data.error) {
                    setStatus(data.error, true);
                }
            } catch (e) {
                console.error(e);
            }
        };

        socket.onclose = (event) => {
            // Codes 4401/4403 are auth errors — don't reconnect
            if (event.code === 4401 || event.code === 4403) {
                setStatus("Not authorized to join this chat", true);
                return;
            }
            const backoff = Math.min(1000 * Math.pow(2, reconnectAttempts), maxBackoff);
            reconnectAttempts++;
            setStatus(`Disconnected — reconnecting in ${backoff/1000}s…`, true);
            setTimeout(connect, backoff);
        };

        socket.onerror = () => {
            setStatus("Connection error", true);
        };
    }

    // --- JS is the key factor: link stays same, data comes as JSON from WSGI/DRF, JS breaks it down ---
    // Fetch history via REST (WSGI) as JSON and render without changing URL (plan §42)
    // URL remains /messages/<id>/ — no ?before in address bar, JS handles pagination in memory
    async function fetchHistory(beforeId = null, appendMode = "replace") {
        try {
            let url = `/api/chat/conversations/${wsId}/messages/?limit=50`;
            if (beforeId) url += `&before=${beforeId}`;
            const res = await fetch(url, {
                headers: { "Accept": "application/json" },
                credentials: "same-origin"
            });
            if (!res.ok) return;
            const data = await res.json();
            // DRF CursorPagination returns {results: [...]}, direct list returns [...]
            const msgs = Array.isArray(data) ? data : (data.results || data);
            if (msgs.length === 0 && appendMode === "prepend") {
                setStatus("No older messages", false);
                return;
            }
            if (appendMode === "replace" && msgs.length > 0) {
                // Clear existing server-rendered (keep empty placeholder if no msgs)
                // But keep URL same — no pushState, just DOM update
                messagesEl.innerHTML = "";
                msgs.forEach(m => {
                    const isOwn = m.sender?.id === parseInt(chatContainer.dataset.currentUserId, 10) ||
                                  m.sender_id === parseInt(chatContainer.dataset.currentUserId, 10) ||
                                  m.sender_registration_id === chatContainer.dataset.currentRegistrationId;
                    appendMessage({
                        id: m.id,
                        content: m.content || m.body || "",
                        body: m.body || m.content || "",
                        sender: m.sender,
                        sender_name: m.sender?.name,
                        sender_id: m.sender?.id || m.sender_id,
                        sender_registration_id: m.sender?.registration_id || m.sender_registration_id,
                        created_at: m.created_at
                    }, isOwn);
                    const last = messagesEl.lastElementChild;
                    if (last) last.setAttribute("data-message-id", m.id);
                });
                scrollToBottom();
            } else if (appendMode === "prepend") {
                // Prepend older messages at top without changing URL (history stays same)
                const scrollHeightBefore = messagesEl.scrollHeight;
                // Remove empty placeholder if present
                const empty = messagesEl.querySelector("[data-empty]");
                if (empty) empty.remove();
                // msgs are in chronological order (oldest first) from service; we need to prepend in order
                // Our service returns oldest first for limit, so we prepend in reverse to keep order
                const fragment = document.createDocumentFragment();
                // Create temp container to build rows, then prepend
                msgs.forEach(m => {
                    const isOwn = m.sender?.id === parseInt(chatContainer.dataset.currentUserId, 10) ||
                                  m.sender_id === parseInt(chatContainer.dataset.currentUserId, 10);
                    // Build row
                    const row = document.createElement("div");
                    row.setAttribute("data-message-id", m.id);
                    row.style.display = "flex";
                    row.style.justifyContent = isOwn ? "flex-end" : "flex-start";
                    const bubble = document.createElement("div");
                    bubble.style.maxWidth = "72%";
                    bubble.style.padding = "10px 14px";
                    bubble.style.borderRadius = "14px";
                    bubble.style.fontSize = "14px";
                    if (isOwn) {
                        bubble.style.background = "var(--coral)";
                        bubble.style.color = "#fff";
                    } else {
                        bubble.style.background = "#fff";
                        bubble.style.border = "1px solid var(--line)";
                    }
                    const text = document.createElement("div");
                    text.innerHTML = (m.content || m.body || "").replace(/\n/g, "<br>");
                    bubble.appendChild(text);
                    const meta = document.createElement("div");
                    meta.style.fontSize = "10px";
                    meta.style.opacity = "0.75";
                    const senderName = m.sender?.name || (isOwn ? "You" : "Seller");
                    const createdAt = m.created_at ? new Date(m.created_at).toLocaleString() : "";
                    meta.textContent = `${senderName} · ${createdAt}`;
                    bubble.appendChild(meta);
                    row.appendChild(bubble);
                    fragment.appendChild(row);
                });
                messagesEl.prepend(fragment);
                // Keep scroll position
                messagesEl.scrollTop = messagesEl.scrollHeight - scrollHeightBefore;
                setStatus(`Loaded ${msgs.length} older messages — link still /messages/${conversationId}/`, false);
            }
        } catch (e) {
            console.error("history fetch failed", e);
        }
    }

    // Load older handler — link stays same, JS fetches ?before via REST and prepends
    const loadOlderBtn = document.querySelector("[data-load-older]");
    if (loadOlderBtn) {
        loadOlderBtn.addEventListener("click", () => {
            const firstMsg = messagesEl.querySelector("[data-message-id]");
            const beforeId = firstMsg ? firstMsg.getAttribute("data-message-id") : null;
            if (!beforeId) {
                setStatus("No older messages", false);
                return;
            }
            // Fetch older via WSGI JSON, JS breaks down and prepends — URL does NOT change
            fetchHistory(beforeId, "prepend");
        });
    }

    // Intercept form submit — ALWAYS via JS (WebSocket or REST fetch), never full page reload
    // → link remains same (/messages/<id>/) while data updates dynamically
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const content = input.value.trim();
        if (!content) return;
        // Prefer WebSocket (real-time)
        if (socket && socket.readyState === WebSocket.OPEN) {
            const payload = {
                type: "message.send",
                content: content,
                message_type: "text"
            };
            socket.send(JSON.stringify(payload));
            input.value = "";
            // Will be appended on message.new broadcast — no URL change
            return;
        }
        // Fallback to REST POST (still JSON, still no URL change)
        try {
            setStatus("Sending via REST…");
            const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
            // Use the traditional view's POST via fetch with same URL, but handle as JSON fallback
            // First try WebSocket-style REST: POST to /api if available, else POST to current page via fetch
            let res = await fetch(`/api/chat/conversations/${wsId}/messages/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrf,
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                credentials: "same-origin",
                body: JSON.stringify({ content: content, message_type: "text" })
            });
            // If API POST not implemented (405), fallback to traditional POST via fetch
            if (res.status === 405 || res.status === 404) {
                const formData = new FormData();
                formData.append("body", content);
                formData.append("csrfmiddlewaretoken", csrf);
                res = await fetch(window.location.pathname, {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                });
                if (res.ok) {
                    // Traditional view redirects, but fetch won't change URL — manually fetch updated history
                    input.value = "";
                    await fetchHistory();
                    setStatus("Sent (fallback) — real-time");
                    return;
                }
            }
            if (res.ok) {
                const data = await res.json().catch(() => null);
                // If API returns message, append directly; else fetch history
                if (data && data.id) {
                    const isOwn = true;
                    appendMessage(data, isOwn);
                    const last = messagesEl.lastElementChild;
                    if (last) last.setAttribute("data-message-id", data.id);
                } else {
                    await fetchHistory();
                }
                input.value = "";
                setStatus("Sent — real-time");
            } else {
                const err = await res.text();
                setStatus(err || "Failed to send", true);
            }
        } catch (err) {
            setStatus("Failed to send", true);
            console.error(err);
        }
    });

    // Initial load: fetch history via WSGI/DRF JSON (link stays same, JS breaks down JSON → HTML)
    // Keep server-rendered as fallback for noscript, but for JS, replace with JSON-driven render
    // Don't use pushState — URL remains /messages/<id>/
    fetchHistory().then(() => {
        connect();
        scrollToBottom();
    });

    // Mark as read via REST when viewing (plan §17) — no URL change
    try {
        fetch(`/api/chat/conversations/${wsId}/read/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")?.value || "",
                "Content-Type": "application/json"
            },
            body: JSON.stringify({}),
            credentials: "same-origin"
        }).catch(()=>{});
    } catch(e) {}

    // Handle pagination without URL change: example “Load older” would do fetch with ?before=<id> via JS, not link navigation
});
