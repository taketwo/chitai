/**
 * Frontend debug shim that forwards console logs to backend.
 *
 * This allows AI agents and developers to see both frontend and backend logs
 * in a single server log stream, making debugging much easier.
 */
(function () {
  const LOG_ENDPOINT = "/api/logs";

  // Store original console methods
  const originalConsole = {
    log: console.log,
    info: console.info,
    warn: console.warn,
    error: console.error,
  };

  /**
   * Send log message to backend.
   * Suppress errors to avoid infinite loops if the endpoint fails.
   */
  async function sendToBackend(level, args) {
    try {
      // Convert arguments to strings for serialization
      const message = args
        .map((arg) => {
          if (typeof arg === "object") {
            try {
              return JSON.stringify(arg);
            } catch {
              return String(arg);
            }
          }
          return String(arg);
        })
        .join(" ");

      await fetch(LOG_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          level: level,
          message: message,
          args: [],
        }),
      });
    } catch (error) {
      // Silently fail - don't log errors from the logging system itself
      // to avoid infinite loops
    }
  }

  /**
   * Intercept console method and forward to backend.
   */
  function interceptConsole(level) {
    console[level] = function (...args) {
      // Call original console method first
      originalConsole[level].apply(console, args);

      // Send to backend (async, non-blocking)
      sendToBackend(level, args);
    };
  }

  // Intercept all console methods
  interceptConsole("log");
  interceptConsole("info");
  interceptConsole("warn");
  interceptConsole("error");
})();
