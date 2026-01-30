/**
 * Alpine.js admin app component
 */
function adminApp() {
  return {
    currentTab: "items",
    items: [],
    sessions: [],

    async init() {
      this.loadTabFromHash();
      window.addEventListener("hashchange", () => this.loadTabFromHash());
      await this.fetchItems();
      await this.fetchSessions();
    },

    loadTabFromHash() {
      const hash = window.location.hash.slice(1);
      if (hash === "items" || hash === "sessions") {
        this.currentTab = hash;
      } else {
        this.currentTab = "items";
      }
    },

    setTab(tab) {
      window.location.hash = tab;
    },

    async fetchItems() {
      try {
        const response = await fetch("/api/items");
        const data = await response.json();
        this.items = data.items;
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

    formatDate(dateString) {
      if (!dateString) {
        return "—";
      }
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
      if (!startedAt || !endedAt) {
        return "—";
      }
      const start = new Date(startedAt);
      const end = new Date(endedAt);
      const durationMs = end - start;
      const durationMinutes = Math.floor(durationMs / 60000);

      if (durationMinutes < 1) {
        return "< 1 min";
      } else if (durationMinutes < 60) {
        return `${durationMinutes} min`;
      } else {
        const hours = Math.floor(durationMinutes / 60);
        const minutes = durationMinutes % 60;
        return minutes > 0 ? `${hours}h ${minutes}min` : `${hours}h`;
      }
    },

    shortenId(id) {
      return id.substring(0, 8);
    },

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
  };
}
