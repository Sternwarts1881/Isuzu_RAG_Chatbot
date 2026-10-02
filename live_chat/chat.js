const params = new URLSearchParams(window.location.search);
const sessionId = params.get("session_id");
const myRole = params.get("role") || "user";   // personel ekranı için ?role=staff

if (!sessionId) {
    document.body.innerHTML = "<p>session_id bulunamadı.</p>";
    throw new Error("session_id missing");
}

const proto = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${proto}://${location.host}/ws/${sessionId}`);
const seen = new Set();

function renderMessage(data) {
    if (data.message_id && seen.has(data.message_id)) return;
    if (data.message_id) seen.add(data.message_id);

    const messages = document.getElementById("messages");
    const div = document.createElement("div");
    const role = ["user", "staff"].includes(data.sender_role) ? data.sender_role : "system";
    div.className = "msg " + role;
    div.textContent = data.message_text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

ws.onopen = async () => {
    // Geçmiş mesajları yükle (özet + "Oturum açıldı" mesajları burada)
    const res = await fetch(`/sessions/${sessionId}/messages`);
    const data = await res.json();
    data.messages.forEach(renderMessage);
};

ws.onmessage = (event) => renderMessage(JSON.parse(event.data));

function sendMessage() {
    const input = document.getElementById("messageText");
    if (!input.value.trim()) return;
    ws.send(JSON.stringify({ sender_role: myRole, message_text: input.value }));
    input.value = "";
}
window.addEventListener("pagehide", () => {
    const payload = new Blob(
        [JSON.stringify({ reason: "Tarayıcı sekmesi kapatıldı" })],
        { type: "application/json" }
    );
    navigator.sendBeacon(`/sessions/${sessionId}/close`, payload);
});