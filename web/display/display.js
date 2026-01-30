function displayApp() {
  return {
    words: [],
    syllables: [],
    currentWordIndex: null,
    showSyllables: true,
    dimReadWords: true,
    dimFutureWords: false,
    ws: null,
    slideState: null,
    animationId: 0,
    slideDirection: "vertical",

    init() {
      this.ws = new ChitaiWebSocket(
        "display",
        {
          onMessage: (data) => this.handleMessage(data),
        },
        {
          statusElement: this.$refs.status,
        },
      );

      // Determine slide direction based on viewport
      this.updateSlideDirection();
      window.addEventListener("resize", () => this.updateSlideDirection());
    },

    get hasWords() {
      return this.words.length > 0;
    },

    get isCompleted() {
      return this.currentWordIndex === null;
    },

    updateSlideDirection() {
      // Slide across the shorter dimension
      this.slideDirection =
        window.innerWidth < window.innerHeight ? "horizontal" : "vertical";
    },

    async animateTextChange(words, syllables, currentWordIndex) {
      const currentAnimationId = ++this.animationId;
      const isCurrentAnimation = () => currentAnimationId === this.animationId;

      const textDisplay = document.getElementById("textDisplay");

      // Wait for CSS transition to complete
      const waitForTransition = () =>
        new Promise((resolve) => {
          const handler = (event) => {
            if (event.propertyName === "transform") {
              textDisplay.removeEventListener("transitionend", handler);
              resolve();
            }
          };
          textDisplay.addEventListener("transitionend", handler);
        });

      // Slide out old text
      this.slideState = `out-${this.slideDirection}`;
      await waitForTransition();

      if (!isCurrentAnimation()) return;

      // Update content while off-screen (no highlight yet)
      this.words = words || [];
      this.syllables = syllables || [];
      this.currentWordIndex = null;

      // Position for slide-in start (off-screen, opposite side)
      // Use nextTick to ensure Alpine applies the class before we force reflow
      this.slideState = `in-${this.slideDirection}`;
      await this.$nextTick();

      // Force reflow so browser registers position before transitioning
      void textDisplay.offsetHeight;

      // Slide in (transition back to neutral position)
      this.slideState = null;
      await waitForTransition();

      if (!isCurrentAnimation()) return;

      // Apply highlight after text has settled
      this.currentWordIndex =
        currentWordIndex !== undefined ? currentWordIndex : null;
    },

    handleMessage(data) {
      if (data.type === "state") {
        const { words, syllables, current_word_index } = data.payload;

        const newIndex =
          current_word_index !== undefined ? current_word_index : null;

        // Detect new item: transition from completed (null) to first word (0)
        const newItemStarted = this.currentWordIndex === null && newIndex === 0;

        if (newItemStarted) {
          this.animateTextChange(words, syllables, current_word_index);
        } else {
          // Just word navigation or completion, update state directly
          this.words = words || [];
          this.syllables = syllables || [];
          this.currentWordIndex = newIndex;
        }
      }
    },
  };
}
