function controllerApp() {
  return {
    connected: false,
    sessionActive: false,
    textInput: "",
    words: [],
    currentWordIndex: null,
    queue: [],
    ws: null,

    init() {
      this.ws = new ChitaiWebSocket(
        "controller",
        {
          onMessage: (data) => this.handleMessage(data),
          onStatusChange: (connected) => this.handleStatusChange(connected),
        },
        {
          statusElement: this.$refs.status,
        },
      );

      // Watch for current word changes and update font size
      this.$watch("currentWord", () => {
        this.$nextTick(() => {
          this.adjustCurrentWordFontSize();
        });
      });
    },

    get currentWord() {
      if (
        this.currentWordIndex !== null &&
        this.words.length > 0 &&
        this.currentWordIndex < this.words.length
      ) {
        return this.words[this.currentWordIndex];
      }
      // When completed, show the last word
      if (this.isCompleted && this.words.length > 0) {
        return this.words[this.words.length - 1];
      }
      return "—";
    },

    get hasWords() {
      return this.words.length > 0;
    },

    get isCompleted() {
      return this.currentWordIndex === null;
    },

    get isLastWord() {
      return (
        this.words.length > 0 &&
        this.currentWordIndex !== null &&
        this.currentWordIndex === this.words.length - 1
      );
    },

    get isNextItemMode() {
      return (this.isLastWord || this.isCompleted) && this.queue.length > 0;
    },

    get advanceButtonLabel() {
      if (this.isCompleted && this.queue.length > 0) {
        return "→"; // Next item
      } else if (this.isLastWord) {
        return "✓"; // Mark complete
      } else {
        return "→"; // Next word
      }
    },

    handleStatusChange(connected) {
      this.connected = connected;
    },

    handleMessage(data) {
      if (data.type === "state") {
        const { session_id, words, current_word_index, queue } = data.payload;

        // Update state
        this.words = words || [];
        this.currentWordIndex =
          current_word_index !== undefined ? current_word_index : null;
        this.queue = queue || [];

        // Update session state
        this.sessionActive = session_id !== null;
      }
    },

    adjustCurrentWordFontSize() {
      const currentWordEl = this.$refs.currentWord;
      if (!currentWordEl) return;

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
    },

    submitAndShow() {
      const text = this.textInput.trim();
      if (text) {
        this.ws.send({
          type: "add_item",
          payload: {
            text: text,
          },
        });
        this.ws.send({
          type: "next_item",
        });
        this.textInput = "";
      }
    },

    submitToQueue() {
      const text = this.textInput.trim();
      if (text) {
        this.ws.send({
          type: "add_item",
          payload: {
            text: text,
          },
        });
        this.textInput = "";
      }
    },

    handleEnter(event) {
      if (!event.shiftKey) {
        this.submitAndShow();
      }
    },

    advanceWord(delta) {
      this.ws.send({
        type: "advance_word",
        payload: {
          delta: delta,
        },
      });
    },

    advance() {
      if (this.isCompleted && this.queue.length > 0) {
        // Completed with queue - advance to next item
        this.ws.send({
          type: "next_item",
        });
      } else {
        // Otherwise advance word (or mark complete if on last word)
        this.advanceWord(1);
      }
    },

    startSession() {
      this.ws.send({
        type: "start_session",
      });
    },

    endSession() {
      this.ws.send({
        type: "end_session",
      });
    },
  };
}
