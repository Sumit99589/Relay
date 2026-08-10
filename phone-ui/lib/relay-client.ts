import type { ConnectionPhase, PhoneMessage, RelayConfig, RelayMessage } from "./protocol";
import { isRelayMessage } from "./protocol";

type RelayClientHandlers = {
  onMessage: (message: RelayMessage) => void;
  onPhaseChange: (phase: ConnectionPhase) => void;
  onProtocolError?: (message: string) => void;
};

const MAX_RECONNECT_DELAY = 30_000;

export function normalizeWebSocketBase(value: string) {
  const trimmed = value.trim().replace(/\/$/, "");
  const withProtocol = /^https?:\/\//i.test(trimmed)
    ? trimmed.replace(/^http/i, "ws")
    : /^(ws|wss):\/\//i.test(trimmed)
      ? trimmed
      : `wss://${trimmed}`;
  return withProtocol.replace(/\/ws\/phone$/i, "");
}

export function toHttpBase(value: string) {
  return normalizeWebSocketBase(value).replace(/^ws/i, "http");
}

export class RelayClient {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectDelay = 1_000;
  private intentionalClose = false;
  private config: RelayConfig | null = null;
  private handlers: RelayClientHandlers;

  constructor(handlers: RelayClientHandlers) {
    this.handlers = handlers;
  }

  connect(config: RelayConfig) {
    this.disconnect();
    this.config = config;
    this.intentionalClose = false;

    if (!config.url || !config.token) {
      this.handlers.onPhaseChange("not_configured");
      return;
    }

    this.open("connecting");
  }

  private open(phase: "connecting" | "reconnecting") {
    if (!this.config) return;
    this.handlers.onPhaseChange(phase);

    let socket: WebSocket;
    try {
      const url = `${normalizeWebSocketBase(this.config.url)}/ws/phone?token=${encodeURIComponent(this.config.token)}`;
      socket = new WebSocket(url);
    } catch {
      this.handlers.onPhaseChange("disconnected");
      return;
    }

    this.socket = socket;

    socket.addEventListener("open", () => {
      if (this.socket !== socket) return;
      this.reconnectDelay = 1_000;
      this.handlers.onPhaseChange("connected");
      this.heartbeatTimer = setInterval(() => this.send({ type: "ping" }), 25_000);
    });

    socket.addEventListener("message", (event) => {
      try {
        const parsed: unknown = JSON.parse(String(event.data));
        if (isRelayMessage(parsed)) this.handlers.onMessage(parsed);
        else this.handlers.onProtocolError?.("The relay sent an unsupported message.");
      } catch {
        this.handlers.onProtocolError?.("The relay sent a message that could not be read.");
      }
    });

    socket.addEventListener("close", (event) => {
      if (this.socket === socket) this.socket = null;
      this.clearHeartbeat();
      if (this.intentionalClose) return;
      if (event.code === 4001) {
        this.handlers.onPhaseChange("auth_failed");
        return;
      }
      this.scheduleReconnect();
    });
  }

  private scheduleReconnect() {
    if (this.intentionalClose || !this.config) return;
    this.handlers.onPhaseChange("reconnecting");
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    const wait = this.reconnectDelay;
    this.reconnectTimer = setTimeout(() => this.open("reconnecting"), wait);
    this.reconnectDelay = Math.min(wait * 2, MAX_RECONNECT_DELAY);
  }

  send(message: PhoneMessage) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(message));
    return true;
  }

  disconnect() {
    this.intentionalClose = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.clearHeartbeat();
    if (this.socket) this.socket.close();
    this.socket = null;
  }

  private clearHeartbeat() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }
}
