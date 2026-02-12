function controllerApp() {
  return {
    connected: false,
    sessionActive: false,
    sessionLanguage: null,
    textInput: "",
    suggestions: [],
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
        const { session_id, language, words, current_word_index, queue } =
          data.payload;

        this.words = words ?? [];
        this.currentWordIndex = current_word_index ?? null;
        this.queue = queue ?? [];
        this.sessionActive = session_id !== null;
        this.sessionLanguage = language ?? null;
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

    async submitAndShow() {
      const text = this.textInput.trim();
      if (!text) return;

      const itemId = await this.resolveItem(text);
      if (!itemId) return;

      this.ws.send({ type: "add_item", payload: { item_id: itemId } });
      this.ws.send({ type: "next_item" });
      this.textInput = "";
      this.suggestions = [];
    },

    async submitToQueue() {
      const text = this.textInput.trim();
      if (!text) return;

      const itemId = await this.resolveItem(text);
      if (!itemId) return;

      this.ws.send({ type: "add_item", payload: { item_id: itemId } });
      this.textInput = "";
      this.suggestions = [];
    },

    async resolveItem(text) {
      if (!this.sessionLanguage) {
        console.error("Cannot resolve item: no session language");
        return null;
      }

      try {
        const formData = new FormData();
        formData.append("text", text);
        formData.append("language", this.sessionLanguage);

        const response = await fetch("/api/items", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          console.error("Failed to resolve item:", response.status);
          return null;
        }

        const data = await response.json();
        return data.id;
      } catch (error) {
        console.error("Error resolving item:", error);
        return null;
      }
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

    async fetchSuggestions() {
      const text = this.textInput.trim();

      // Clear suggestions if text is too short
      if (text.length < 3) {
        this.suggestions = [];
        return;
      }

      // Need session language for autocomplete
      if (!this.sessionLanguage) {
        this.suggestions = [];
        return;
      }

      try {
        const params = new URLSearchParams({
          text: text,
          language: this.sessionLanguage,
          limit: "3",
        });

        const response = await fetch(`/api/items/autocomplete?${params}`);
        if (!response.ok) {
          console.warn("Autocomplete request failed:", response.status);
          this.suggestions = [];
          return;
        }

        const data = await response.json();
        this.suggestions = data.suggestions || [];
      } catch (error) {
        console.error("Autocomplete error:", error);
        this.suggestions = [];
      }
    },

    selectSuggestion(text) {
      this.textInput = text;
      this.suggestions = [];
    },
  };
}
