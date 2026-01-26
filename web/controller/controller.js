const statusEl = document.getElementById("status");
const textInput = document.getElementById("textInput");
const submitBtn = document.getElementById("submitBtn");
const backBtn = document.getElementById("backBtn");
const advanceBtn = document.getElementById("advanceBtn");
const currentWordEl = document.getElementById("currentWord");
const startSessionBtn = document.getElementById("startSessionBtn");
const endSessionBtn = document.getElementById("endSessionBtn");

let sessionActive = false;
let currentState = {
  words: [],
  current_word_index: 0,
  queue: [],
};

const ws = new ChitaiWebSocket(
  "controller",
  {
    onMessage: handleMessage,
    onStatusChange: handleStatusChange,
  },
  {
    statusElement: statusEl,
  },
);

function handleStatusChange(connected) {
  if (connected) {
    startSessionBtn.disabled = false;
  } else {
    startSessionBtn.disabled = true;
    endSessionBtn.disabled = true;
    submitBtn.disabled = true;
    backBtn.disabled = true;
    advanceBtn.disabled = true;
  }
}

function handleMessage(data) {
  if (data.type === "state") {
    const { session_id, words, current_word_index, queue } = data.payload;

    // Update current state
    currentState = {
      words: words || [],
      current_word_index: current_word_index || 0,
      queue: queue || [],
    };

    // Update session state based on session_id presence
    const wasActive = sessionActive;
    sessionActive = session_id !== null;

    // Update UI if session state changed
    if (sessionActive && !wasActive) {
      // Session started
      startSessionBtn.style.display = "none";
      endSessionBtn.style.display = "block";
      endSessionBtn.disabled = false;
      submitBtn.disabled = false;
      backBtn.disabled = false;
      advanceBtn.disabled = false;
    } else if (!sessionActive && wasActive) {
      // Session ended
      startSessionBtn.style.display = "block";
      startSessionBtn.disabled = false;
      endSessionBtn.style.display = "none";
      submitBtn.disabled = true;
      backBtn.disabled = true;
      advanceBtn.disabled = true;
      document.querySelector(".controls").style.display = "none";
    }
    if (words && words.length > 0) {
      document.querySelector(".controls").style.display = "flex";
      updateCurrentWord(words[current_word_index]);
      updateAdvanceButton();
    } else {
      document.querySelector(".controls").style.display = "none";
    }
  }
}

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

function updateAdvanceButton() {
  const isLastWord =
    currentState.words.length > 0 &&
    currentState.current_word_index === currentState.words.length - 1;
  const hasQueue = currentState.queue.length > 0;

  if (isLastWord && hasQueue) {
    // On last word with items in queue - show "next item" mode with green color
    advanceBtn.classList.add("next-item");
  } else {
    // Not on last word or no queue - show normal "next word" mode
    advanceBtn.classList.remove("next-item");
  }
}

submitBtn.addEventListener("click", () => {
  const text = textInput.value.trim();
  if (text) {
    const message = {
      type: "add_item",
      payload: {
        text: text,
      },
    };
    ws.send(message);
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
  ws.send(message);
  console.log("Sent:", message);
});

advanceBtn.addEventListener("click", () => {
  const isLastWord =
    currentState.words.length > 0 &&
    currentState.current_word_index === currentState.words.length - 1;
  const hasQueue = currentState.queue.length > 0;

  let message;
  if (isLastWord && hasQueue) {
    // On last word with queue - send next_item
    message = {
      type: "next_item",
    };
  } else {
    // Otherwise send advance_word
    message = {
      type: "advance_word",
      payload: {
        delta: 1,
      },
    };
  }
  ws.send(message);
  console.log("Sent:", message);
});

startSessionBtn.addEventListener("click", () => {
  const message = {
    type: "start_session",
  };
  ws.send(message);
  console.log("Sent:", message);
});

endSessionBtn.addEventListener("click", () => {
  const message = {
    type: "end_session",
  };
  ws.send(message);
  console.log("Sent:", message);
});
