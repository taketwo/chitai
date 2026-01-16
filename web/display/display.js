const statusEl = document.getElementById("status");
const textDisplay = document.getElementById("textDisplay");

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const ws = new WebSocket(
  `${protocol}//${window.location.host}/ws?role=display`,
);

ws.onopen = () => {
  console.log("Connected");
  statusEl.textContent = "Connected";
  statusEl.className = "status connected";
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);

  if (data.type === "state") {
    const text = data.payload.current_text;
    if (text) {
      textDisplay.innerHTML = text;
    } else {
      textDisplay.innerHTML =
        '<span class="placeholder">Waiting for text...</span>';
    }
  }
};

ws.onclose = () => {
  console.log("Disconnected");
  statusEl.textContent = "Disconnected";
  statusEl.className = "status disconnected";
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};
