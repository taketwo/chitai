const statusEl = document.getElementById("status");
const textInput = document.getElementById("textInput");
const submitBtn = document.getElementById("submitBtn");
const backBtn = document.getElementById("backBtn");
const advanceBtn = document.getElementById("advanceBtn");
const currentWordEl = document.getElementById("currentWord");

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const ws = new WebSocket(
  `${protocol}//${window.location.host}/ws?role=controller`,
);

ws.onopen = () => {
  console.log("Connected");
  statusEl.textContent = "Connected";
  statusEl.className = "status connected";
  submitBtn.disabled = false;
  backBtn.disabled = false;
  advanceBtn.disabled = false;
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);

  if (data.type === "state") {
    const { words, current_word_index } = data.payload;
    if (words && words.length > 0) {
      document.querySelector(".controls").style.display = "flex";
      updateCurrentWord(words[current_word_index]);
    } else {
      document.querySelector(".controls").style.display = "none";
    }
  }
};

function updateCurrentWord(word) {
  currentWordEl.textContent = word;

  // Reset to default font size
  const defaultFontSize = 32;
  currentWordEl.style.fontSize = `${defaultFontSize}px`;

  // Need a slight delay for browser to reflow
  requestAnimationFrame(() => {
    const containerWidth = currentWordEl.offsetWidth;
    let textWidth = currentWordEl.scrollWidth;

    if (textWidth > containerWidth) {
      let fontSize = defaultFontSize;
      let attempts = 0;
      const maxAttempts = 3;

      while (
        textWidth > containerWidth &&
        attempts < maxAttempts &&
        fontSize > 12
      ) {
        // Calculate new font size based on current measurements
        const scaleFactor = containerWidth / textWidth;
        fontSize = Math.floor(fontSize * scaleFactor * 0.95); // 95% of calculated to be safe
        fontSize = Math.max(fontSize, 12); // Min 12px

        // Apply and re-measure
        currentWordEl.style.fontSize = `${fontSize}px`;
        textWidth = currentWordEl.scrollWidth;
        attempts++;
      }
    }
  });
}

ws.onclose = () => {
  console.log("Disconnected");
  statusEl.textContent = "Disconnected";
  statusEl.className = "status disconnected";
  submitBtn.disabled = true;
  backBtn.disabled = true;
  advanceBtn.disabled = true;
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

backBtn.addEventListener("click", () => {
  const message = {
    type: "advance_word",
    payload: {
      delta: -1,
    },
  };
  ws.send(JSON.stringify(message));
  console.log("Sent:", message);
});

advanceBtn.addEventListener("click", () => {
  const message = {
    type: "advance_word",
    payload: {
      delta: 1,
    },
  };
  ws.send(JSON.stringify(message));
  console.log("Sent:", message);
});
