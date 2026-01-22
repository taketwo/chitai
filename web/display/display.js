const statusEl = document.getElementById("status");
const textDisplay = document.getElementById("textDisplay");

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const ws = new WebSocket(
  `${protocol}//${window.location.host}/ws?role=display`,
);

let isPageUnloading = false;
window.addEventListener("beforeunload", () => {
  isPageUnloading = true;
});

// Show disconnected indicator only if connection takes too long or fails
let connectionTimeout = setTimeout(() => {
  if (statusEl.className !== "status connected") {
    statusEl.className = "status disconnected";
  }
}, 1000); // 1 second grace period

ws.onopen = () => {
  console.log("Connected");
  clearTimeout(connectionTimeout);
  statusEl.className = "status connected";
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);

  if (data.type === "state") {
    const { words, syllables, current_word_index } = data.payload;
    if (words && words.length > 0) {
      renderWords(words, syllables, current_word_index);
    } else {
      textDisplay.innerHTML = '<span class="placeholder"></span>';
    }
  }
};

function renderWords(words, syllables, currentIndex) {
  // Settings (hardcoded for now)
  const showSyllables = true;
  const dimReadWords = true;
  const dimFutureWords = false;

  textDisplay.innerHTML = "";

  words.forEach((word, index) => {
    const wordEl = document.createElement("div");
    wordEl.className = "word";

    // Render word with or without syllables
    if (showSyllables) {
      const wordSyllables = syllables[index] || [word];
      wordSyllables.forEach((syllable, sylIndex) => {
        const syllableSpan = document.createElement("span");
        syllableSpan.textContent = syllable;
        syllableSpan.className = "syllable";

        // Add separator class for all but the last syllable
        if (sylIndex < wordSyllables.length - 1) {
          syllableSpan.classList.add("syllable-with-separator");
        }

        wordEl.appendChild(syllableSpan);
      });
    } else {
      wordEl.textContent = word;
    }

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
  if (!isPageUnloading) {
    statusEl.className = "status disconnected";
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};
