const statusEl = document.getElementById("status");
const textInput = document.getElementById("textInput");
const submitBtn = document.getElementById("submitBtn");

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const ws = new WebSocket(
  `${protocol}//${window.location.host}/ws?role=controller`,
);

ws.onopen = () => {
  console.log("Connected");
  statusEl.textContent = "Connected";
  statusEl.className = "status connected";
  submitBtn.disabled = false;
};

ws.onmessage = (event) => {
  console.log("Received:", event.data);
};

ws.onclose = () => {
  console.log("Disconnected");
  statusEl.textContent = "Disconnected";
  statusEl.className = "status disconnected";
  submitBtn.disabled = true;
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

submitBtn.addEventListener("click", () => {
  const text = textInput.value.trim();
  if (text) {
    const message = {
      type: "add_item",
      payload: {
        text: text,
      },
    };
    ws.send(JSON.stringify(message));
    console.log("Sent:", message);
    textInput.value = "";
  }
});

// Allow Enter to submit (Shift+Enter for newline)
textInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitBtn.click();
  }
});
