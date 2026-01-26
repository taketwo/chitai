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
   * @param {HTMLElement} options.statusElement - Optional status indicator element to manage
   */
  constructor(role, callbacks, options = {}) {
    this.role = role;
    this.callbacks = callbacks;
    this.statusElement = options.statusElement;
    this.ws = null;
    this.isPageUnloading = false;
    this.connectionTimeout = null;

    this._setupPageUnloadHandler();
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
  }

  /**
   * Handle WebSocket error event.
   */
  _handleError(error) {
    console.error("WebSocket error:", error);
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
   */
  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
