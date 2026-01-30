/**
 * Alpine.js admin app component
 */
function adminApp() {
  return {
    currentTab: "items",
    items: [],
    sessions: [],

    async init() {
      await this.fetchItems();
      await this.fetchSessions();
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
  };
}
