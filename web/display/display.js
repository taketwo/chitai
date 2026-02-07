function displayApp() {
  return {
    // State
    words: [],
    syllables: [],
    currentWordIndex: null,
    illustrationId: null,
    ws: null,

    // Display settings
    showSyllables: true,
    dimReadWords: true,
    dimFutureWords: false,

    // Animation state
    slideState: null,
    animationId: 0,
    slideDirection: "vertical",
    orientation: "landscape",
    illustrationVisible: false,

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

      this.updateOrientation();
      window.addEventListener("resize", () => this.updateOrientation());
    },

    get hasWords() {
      return this.words.length > 0;
    },

    get isCompleted() {
      return this.currentWordIndex === null;
    },

    get illustrationUrl() {
      return this.illustrationId
        ? `/api/illustrations/${this.illustrationId}/image`
        : null;
    },

    updateOrientation() {
      this.orientation =
        window.innerWidth < window.innerHeight ? "portrait" : "landscape";
      this.updateSlideDirection();
    },

    handleMessage(data) {
      if (data.type === "state") {
        const { words, syllables, current_word_index, illustration_id } =
          data.payload;

        const newIndex = current_word_index ?? null;
        const newIllustrationId = illustration_id ?? null;

        // Detect new item: transition from completed (null) to first word (0)
        const newItemStarted = this.currentWordIndex === null && newIndex === 0;

        if (newItemStarted) {
          this.animateTextChange(words, syllables, newIndex, newIllustrationId);
        } else {
          // Just word navigation or completion, update state directly
          this.words = words ?? [];
          this.syllables = syllables ?? [];
          this.currentWordIndex = newIndex;
          this.illustrationId = newIllustrationId;

          // Show illustration when item completes
          if (this.isCompleted && this.illustrationId) {
            this.illustrationVisible = true;
          }
        }
      }
    },

    updateSlideDirection() {
      // Slide across the shorter dimension
      this.slideDirection =
        window.innerWidth < window.innerHeight ? "horizontal" : "vertical";
    },

    async animateTextChange(
      words,
      syllables,
      currentWordIndex,
      illustrationId,
    ) {
      this.animationId += 1;
      const currentAnimationId = this.animationId;
      const isCurrentAnimation = () => currentAnimationId === this.animationId;

      const textDisplay = document.getElementById("textDisplay");
      if (!textDisplay) return;

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

      // Slide out old text and fade out illustration simultaneously
      this.slideState = `out-${this.slideDirection}`;
      this.illustrationVisible = false;
      await waitForTransition();

      if (!isCurrentAnimation()) return;

      // Update content while off-screen (no highlight yet)
      this.words = words ?? [];
      this.syllables = syllables ?? [];
      this.currentWordIndex = null;
      this.illustrationId = illustrationId ?? null;

      // Pre-fetch illustration if present
      if (this.illustrationId) {
        const img = new Image();
        img.src = this.illustrationUrl;
      }

      // Position for slide-in start (off-screen, opposite side)
      this.slideState = `in-${this.slideDirection}`;
      await this.$nextTick();

      // Force reflow to register position before transition
      // eslint-disable-next-line no-unused-expressions
      textDisplay.offsetHeight;

      // Slide in (transition back to neutral position)
      this.slideState = null;
      await waitForTransition();

      if (!isCurrentAnimation()) return;

      // Apply highlight after text has settled
      this.currentWordIndex = currentWordIndex ?? null;
    },
  };
}
