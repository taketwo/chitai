function displayApp() {
  return {
    words: [],
    syllables: [],
    currentWordIndex: 0,
    showSyllables: true,
    dimReadWords: true,
    dimFutureWords: false,
    ws: null,

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
    },

    get hasWords() {
      return this.words.length > 0;
    },

    handleMessage(data) {
      if (data.type === "state") {
        const { words, syllables, current_word_index } = data.payload;

        // Update state
        this.words = words || [];
        this.syllables = syllables || [];
        this.currentWordIndex = current_word_index || 0;
      }
    },
  };
}
