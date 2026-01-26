/**
 * Shared WebSocket connection manager for Chitai client applications.
 *
 * Handles connection lifecycle, status indicators, and message handling
 * with a clean callback-based API.
 */
class ChitaiWebSocket {
  /**
   * Create a new WebSocket connection manager.
   *
   * @param {string} role - The client role ('controller', 'display', etc.)
   * @param {Object} callbacks - Callback functions for WebSocket events
   * @param {Function} callbacks.onMessage - Called when a message is received (data)
   * @param {Function} callbacks.onStatusChange - Called when connection status changes (isConnected)
   * @param {Object} options - Configuration options
   * @param {HTMLElement} options.statusElement - Optional status indicator element to manage
   * @param {boolean} options.autoReconnect - Enable automatic reconnection (default: true)
   * @param {number} options.reconnectInterval - Base reconnection interval in ms (default: 1000)
   * @param {number} options.maxReconnectInterval - Maximum reconnection interval in ms (default: 30000)
   */
  constructor(role, callbacks, options = {}) {
    this.role = role;
    this.callbacks = callbacks;
    this.statusElement = options.statusElement;
    this.autoReconnect = options.autoReconnect ?? true;
    this.reconnectInterval = options.reconnectInterval ?? 1000;
    this.maxReconnectInterval = options.maxReconnectInterval ?? 30000;

    this.ws = null;
    this.isPageUnloading = false;
    this.connectionTimeout = null;
    this.reconnectTimeout = null;
    this.currentReconnectInterval = this.reconnectInterval;

    this._setupPageUnloadHandler();
    this._setupVisibilityChangeHandler();
    this._connect();
  }

  /**
   * Setup handler to track page unload state.
   * Prevents showing disconnected indicator during normal navigation.
   */
  _setupPageUnloadHandler() {
    window.addEventListener("beforeunload", () => {
      this.isPageUnloading = true;
    });
  }

  /**
   * Setup handler to detect when page becomes visible.
   * Triggers immediate reconnection if disconnected when user returns to page.
   */
  _setupVisibilityChangeHandler() {
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        // Page became visible - if we're disconnected, reconnect immediately
        if (
          this.autoReconnect &&
          (!this.ws || this.ws.readyState !== WebSocket.OPEN)
        ) {
          console.log(
            "Page visible and disconnected - reconnecting immediately",
          );
          // Clear any pending reconnect timeout
          if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
          }
          // Reset backoff interval for immediate retry
          this.currentReconnectInterval = this.reconnectInterval;
          this._connect();
        }
      }
    });
  }

  /**
   * Establish WebSocket connection.
   */
  _connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws?role=${this.role}`;

    this.ws = new WebSocket(url);

    // Show disconnected indicator only if connection takes too long
    this.connectionTimeout = setTimeout(() => {
      if (
        this.statusElement &&
        this.statusElement.className !== "status connected"
      ) {
        this.statusElement.className = "status disconnected";
      }
    }, 1000); // 1 second grace period

    this.ws.onopen = () => this._handleOpen();
    this.ws.onmessage = (event) => this._handleMessage(event);
    this.ws.onclose = () => this._handleClose();
    this.ws.onerror = (error) => this._handleError(error);
  }

  /**
   * Handle WebSocket open event.
   */
  _handleOpen() {
    console.log("Connected");
    clearTimeout(this.connectionTimeout);

    // Reset reconnection interval on successful connection
    this.currentReconnectInterval = this.reconnectInterval;

    if (this.statusElement) {
      this.statusElement.className = "status connected";
    }

    if (this.callbacks.onStatusChange) {
      this.callbacks.onStatusChange(true);
    }
  }

  /**
   * Handle incoming WebSocket message.
   */
  _handleMessage(event) {
    try {
      const data = JSON.parse(event.data);
      console.log("Received:", data);

      if (this.callbacks.onMessage) {
        this.callbacks.onMessage(data);
      }
    } catch (error) {
      console.error("Failed to parse message:", error);
    }
  }

  /**
   * Handle WebSocket close event.
   */
  _handleClose() {
    console.log("Disconnected");

    if (!this.isPageUnloading && this.statusElement) {
      this.statusElement.className = "status disconnected";
    }

    if (this.callbacks.onStatusChange) {
      this.callbacks.onStatusChange(false);
    }

    // Attempt to reconnect if enabled and not unloading
    if (this.autoReconnect && !this.isPageUnloading) {
      this._scheduleReconnect();
    }
  }

  /**
   * Handle WebSocket error event.
   */
  _handleError(error) {
    console.error("WebSocket error:", error);
  }

  /**
   * Schedule a reconnection attempt with exponential backoff.
   */
  _scheduleReconnect() {
    // Clear any existing reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }

    console.log(
      `Reconnecting in ${this.currentReconnectInterval / 1000} seconds...`,
    );

    this.reconnectTimeout = setTimeout(() => {
      console.log("Attempting to reconnect...");
      this._connect();

      // Exponential backoff: double the interval for next attempt (up to max)
      this.currentReconnectInterval = Math.min(
        this.currentReconnectInterval * 2,
        this.maxReconnectInterval,
      );
    }, this.currentReconnectInterval);
  }

  /**
   * Send a message through the WebSocket connection.
   *
   * @param {Object} message - The message object to send
   */
  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      console.log("Sent:", message);
    } else {
      console.error("WebSocket is not connected");
    }
  }

  /**
   * Close the WebSocket connection.
   * Disables auto-reconnect to prevent reconnection after manual close.
   */
  close() {
    this.autoReconnect = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
    }
  }
}
