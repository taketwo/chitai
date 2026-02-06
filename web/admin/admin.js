/**
 * Alpine.js admin app component
 */
function adminApp() {
  return {
    // Tab state
    currentTab: "items",

    // Data
    items: [],
    sessions: [],
    illustrations: [],

    // Import controls
    urlInput: "",

    // Item modal state
    itemModalVisible: false,
    modalItem: null,
    modalLinkedIllustrations: [],

    // Illustration picker state
    pickerVisible: false,
    availableIllustrationsForPicker: [],

    // Illustration modal state
    illustrationModalVisible: false,
    modalIllustration: null,

    async init() {
      this.loadTabFromHash();
      window.addEventListener("hashchange", () => this.loadTabFromHash());
      await Promise.all([
        this.fetchItems(),
        this.fetchSessions(),
        this.fetchIllustrations(),
      ]);
    },

    // Tab management

    loadTabFromHash() {
      const hash = window.location.hash.slice(1);
      const validTabs = ["items", "sessions", "illustrations"];
      this.currentTab = validTabs.includes(hash) ? hash : "items";
    },

    setTab(tab) {
      window.location.hash = tab;
    },

    // Data fetching

    async fetchItems() {
      try {
        const response = await fetch("/api/items");
        const data = await response.json();

        const itemsWithCounts = await Promise.all(
          data.items.map(async (item) => {
            try {
              const illustrationsResponse = await fetch(
                `/api/items/${item.id}/illustrations`,
              );
              const illustrations = await illustrationsResponse.json();
              return { ...item, illustration_count: illustrations.length };
            } catch (error) {
              console.error(
                `Failed to fetch illustrations for item ${item.id}:`,
                error,
              );
              return { ...item, illustration_count: 0 };
            }
          }),
        );

        this.items = itemsWithCounts;
      } catch (error) {
        console.error("Failed to fetch items:", error);
      }
    },

    async fetchSessions() {
      try {
        const response = await fetch("/api/sessions");
        const data = await response.json();
        this.sessions = data.sessions;
      } catch (error) {
        console.error("Failed to fetch sessions:", error);
      }
    },

    async fetchIllustrations() {
      try {
        const response = await fetch("/api/illustrations?limit=100");
        const data = await response.json();
        this.illustrations = data.illustrations;
      } catch (error) {
        console.error("Failed to fetch illustrations:", error);
      }
    },

    // Formatters

    formatDate(dateString) {
      if (!dateString) return "—";

      const date = new Date(dateString);
      const months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
      ];
      const month = months[date.getMonth()];
      const day = date.getDate();
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      return `${month} ${day}, ${hours}:${minutes}`;
    },

    formatDuration(startedAt, endedAt) {
      if (!startedAt || !endedAt) return "—";

      const durationMs = new Date(endedAt) - new Date(startedAt);
      const durationMinutes = Math.floor(durationMs / 60000);

      if (durationMinutes < 1) return "< 1 min";
      if (durationMinutes < 60) return `${durationMinutes} min`;

      const hours = Math.floor(durationMinutes / 60);
      const minutes = durationMinutes % 60;
      return minutes > 0 ? `${hours}h ${minutes}min` : `${hours}h`;
    },

    formatFileSize(bytes) {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    },

    // Delete operations

    async handleDelete(url, resourceType) {
      try {
        const response = await fetch(url, { method: "DELETE" });

        if (!response.ok) {
          const error = await response.json();
          console.error(`Failed to delete ${resourceType}:`, error);
          alert(`Failed to delete ${resourceType}. See console for details.`);
        }

        return response.ok;
      } catch (error) {
        console.error(`Failed to delete ${resourceType}:`, error);
        alert(`Failed to delete ${resourceType}. See console for details.`);
        return false;
      }
    },

    async deleteItem(itemId) {
      if (
        !confirm(
          "Delete this item? This will also remove it from all session histories.",
        )
      ) {
        return;
      }

      const success = await this.handleDelete(`/api/items/${itemId}`, "item");
      if (success) {
        this.items = this.items.filter((item) => item.id !== itemId);
      }
    },

    async deleteSession(sessionId) {
      if (!confirm("Delete this session?")) {
        return;
      }

      const success = await this.handleDelete(
        `/api/sessions/${sessionId}`,
        "session",
      );
      if (success) {
        this.sessions = this.sessions.filter(
          (session) => session.id !== sessionId,
        );
      }
    },

    async deleteIllustration(illustrationId) {
      if (
        !confirm(
          "Delete this illustration? This will unlink it from all items and remove the files.",
        )
      ) {
        return;
      }

      const success = await this.handleDelete(
        `/api/illustrations/${illustrationId}`,
        "illustration",
      );
      if (success) {
        this.illustrations = this.illustrations.filter(
          (illustration) => illustration.id !== illustrationId,
        );
      }
    },

    // Import illustrations

    async importIllustrationFromUrl() {
      if (!this.urlInput.trim()) return;

      try {
        const formData = new FormData();
        formData.append("url", this.urlInput.trim());

        const response = await fetch("/api/illustrations", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          console.error("Failed to import illustration:", error);
          alert(
            `Failed to import illustration: ${error.detail || "Unknown error"}`,
          );
          return;
        }

        this.urlInput = "";
        await this.fetchIllustrations();
      } catch (error) {
        console.error("Failed to import illustration:", error);
        alert("Failed to import illustration. See console for details.");
      }
    },

    async importIllustrationFromFile(event) {
      const file = event.target.files[0];
      if (!file) return;

      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("/api/illustrations", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          console.error("Failed to import illustration:", error);
          alert(
            `Failed to import illustration: ${error.detail || "Unknown error"}`,
          );
          return;
        }

        event.target.value = "";
        await this.fetchIllustrations();
      } catch (error) {
        console.error("Failed to import illustration:", error);
        alert("Failed to import illustration. See console for details.");
      }
    },

    // Item modal

    async openItemModal(item, event) {
      if (event.target.closest(".delete-btn")) return;

      this.modalItem = item;
      this.itemModalVisible = true;

      try {
        const response = await fetch(`/api/items/${item.id}/illustrations`);
        this.modalLinkedIllustrations = await response.json();
      } catch (error) {
        console.error("Failed to fetch item illustrations:", error);
        this.modalLinkedIllustrations = [];
      }
    },

    closeItemModal() {
      this.itemModalVisible = false;
      this.modalItem = null;
      this.modalLinkedIllustrations = [];
    },

    // Illustration modal

    openIllustrationModal(illustration, event) {
      if (event.target.closest(".delete-btn")) return;

      this.modalIllustration = illustration;
      this.illustrationModalVisible = true;
    },

    closeIllustrationModal() {
      this.illustrationModalVisible = false;
      this.modalIllustration = null;
    },

    // Illustration picker

    openIllustrationPicker() {
      const linkedIds = new Set(
        this.modalLinkedIllustrations.map((ill) => ill.id),
      );
      this.availableIllustrationsForPicker = this.illustrations.filter(
        (ill) => !linkedIds.has(ill.id),
      );
      this.pickerVisible = true;
    },

    closeIllustrationPicker() {
      this.pickerVisible = false;
      this.availableIllustrationsForPicker = [];
    },

    async linkIllustration(illustrationId) {
      if (!this.modalItem) return;

      try {
        const response = await fetch(
          `/api/items/${this.modalItem.id}/illustrations/${illustrationId}`,
          { method: "POST" },
        );

        if (!response.ok) {
          const error = await response.json();
          console.error("Failed to link illustration:", error);
          alert(
            `Failed to link illustration: ${error.detail || "Unknown error"}`,
          );
          return;
        }

        this.closeIllustrationPicker();

        const linkedResponse = await fetch(
          `/api/items/${this.modalItem.id}/illustrations`,
        );
        this.modalLinkedIllustrations = await linkedResponse.json();

        const item = this.items.find((i) => i.id === this.modalItem.id);
        if (item) {
          item.illustration_count = this.modalLinkedIllustrations.length;
        }
      } catch (error) {
        console.error("Failed to link illustration:", error);
        alert("Failed to link illustration. See console for details.");
      }
    },

    // Link/unlink illustrations

    async unlinkIllustration(itemId, illustrationId) {
      try {
        const response = await fetch(
          `/api/items/${itemId}/illustrations/${illustrationId}`,
          { method: "DELETE" },
        );

        if (!response.ok) {
          const error = await response.json();
          console.error("Failed to unlink illustration:", error);
          alert(
            `Failed to unlink illustration: ${error.detail || "Unknown error"}`,
          );
          return;
        }

        const linkedResponse = await fetch(
          `/api/items/${itemId}/illustrations`,
        );
        this.modalLinkedIllustrations = await linkedResponse.json();

        const item = this.items.find((i) => i.id === itemId);
        if (item) {
          item.illustration_count = this.modalLinkedIllustrations.length;
        }
      } catch (error) {
        console.error("Failed to unlink illustration:", error);
        alert("Failed to unlink illustration. See console for details.");
      }
    },
  };
}
