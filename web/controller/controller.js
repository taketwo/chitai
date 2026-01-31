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
      if (this.currentWordIndex !== null && this.words[this.currentWordIndex]) {
        return this.words[this.currentWordIndex];
      }
      if (this.isCompleted && this.hasWords) {
        return this.words.join(" ");
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
        this.hasWords &&
        this.currentWordIndex !== null &&
        this.currentWordIndex === this.words.length - 1
      );
    },

    get isNextItemMode() {
      return this.isCompleted && this.queue.length > 0;
    },

    get advanceButtonIcon() {
      if (this.isNextItemMode) return "chevron-double-right";
      if (this.isLastWord) return "check";
      return "arrow-right";
    },

    handleStatusChange(connected) {
      this.connected = connected;
    },

    handleMessage(data) {
      if (data.type === "state") {
        const { session_id, words, current_word_index, queue } = data.payload;

        this.words = words ?? [];
        this.currentWordIndex = current_word_index ?? null;
        this.queue = queue ?? [];
        this.sessionActive = session_id !== null;
      }
    },

    adjustCurrentWordFontSize() {
      const currentWordEl = this.$refs.currentWord;
      if (!currentWordEl) return;

      const DEFAULT_FONT_SIZE = 24;
      const MIN_FONT_SIZE = 12;
      const MAX_ATTEMPTS = 3;
      const SCALE_SAFETY_FACTOR = 0.95;

      // Reset to default font size
      currentWordEl.style.fontSize = `${DEFAULT_FONT_SIZE}px`;

      // Need a slight delay for browser to reflow
      requestAnimationFrame(() => {
        const containerWidth = currentWordEl.offsetWidth;
        let textWidth = currentWordEl.scrollWidth;

        if (textWidth > containerWidth) {
          let fontSize = DEFAULT_FONT_SIZE;
          let attempts = 0;

          while (
            textWidth > containerWidth &&
            attempts < MAX_ATTEMPTS &&
            fontSize > MIN_FONT_SIZE
          ) {
            // Calculate new font size based on current measurements
            const scaleFactor = containerWidth / textWidth;
            fontSize = Math.floor(fontSize * scaleFactor * SCALE_SAFETY_FACTOR);
            fontSize = Math.max(fontSize, MIN_FONT_SIZE);

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
      if (!text) return;

      this.ws.send({ type: "add_item", payload: { text } });
      this.ws.send({ type: "next_item" });
      this.textInput = "";
    },

    submitToQueue() {
      const text = this.textInput.trim();
      if (!text) return;

      this.ws.send({ type: "add_item", payload: { text } });
      this.textInput = "";
    },

    handleEnter(event) {
      if (!event.shiftKey) {
        this.submitAndShow();
      }
    },

    advanceWord(delta) {
      this.ws.send({ type: "advance_word", payload: { delta } });
    },

    advance() {
      if (this.isNextItemMode) {
        this.ws.send({ type: "next_item" });
      } else {
        this.advanceWord(1);
      }
    },

    startSession() {
      this.ws.send({ type: "start_session" });
    },

    endSession() {
      this.ws.send({ type: "end_session" });
    },
  };
}
