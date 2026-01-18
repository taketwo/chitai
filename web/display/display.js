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
    const { words, current_word_index } = data.payload;
    if (words && words.length > 0) {
      renderWords(words, current_word_index);
    } else {
      textDisplay.innerHTML =
        '<span class="placeholder">Waiting for text...</span>';
    }
  }
};

function renderWords(words, currentIndex) {
  // Settings (hardcoded for now)
  const dimReadWords = true;
  const dimFutureWords = false;

  textDisplay.innerHTML = "";

  words.forEach((word, index) => {
    const wordEl = document.createElement("div");
    wordEl.className = "word";
    wordEl.textContent = word;

    if (index < currentIndex) {
      wordEl.classList.add("read");
      if (dimReadWords) {
        wordEl.classList.add("dimmed");
      }
    } else if (index === currentIndex) {
      wordEl.classList.add("current");
    } else {
      wordEl.classList.add("future");
      if (dimFutureWords) {
        wordEl.classList.add("dimmed");
      }
    }

    textDisplay.appendChild(wordEl);
  });
}

ws.onclose = () => {
  console.log("Disconnected");
  statusEl.textContent = "Disconnected";
  statusEl.className = "status disconnected";
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};
