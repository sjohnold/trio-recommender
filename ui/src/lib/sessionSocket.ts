export type EventKind = 'chunk' | 'utterance' | 'state' | 'metric' | 'error';
export interface SocketEvent {
  sequence: number; kind: EventKind; payload: unknown;
}
export interface SessionCallbacks {
  chunk(event: SocketEvent): void;
  utterance(event: SocketEvent): void;
  state(event: SocketEvent): void;
  metric(event: SocketEvent): void;
  error(error: Error): void;
}
interface WebSocketLike {
  readyState: number; onmessage: ((event: { data: string }) => void) | null;
  onopen?: (() => void) | null;
  onclose: (() => void) | null;
  send(data: string): void;
  close(): void;
}
type SocketFactory = (path: string) => WebSocketLike;
const browserSocket: SocketFactory = path => {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(`${protocol}//${location.host}${path}`);
};
export class SessionSocket {
  private socket?: WebSocketLike;
  private lastSequence = 0;
  private active = true;
  private pending: string[] = [];
  constructor(
    private readonly path: string,
    private readonly callbacks: SessionCallbacks,
    private readonly factory: SocketFactory = browserSocket,
    private readonly schedule: (callback: () => void) => void =
      callback => { setTimeout(callback, 500); }
  ) {
    if (!path.startsWith('/') || /^(?:ws|wss|http|https):/i.test(path)) {
      throw new TypeError('WebSocket path must be same-origin relative');
    }
    this.connect();
  }
  private connect() {
    if (!this.active) return;
    const socket = this.factory(this.path);
    this.socket = socket;
    this.lastSequence = 0;
    socket.onopen = () => {
      if (this.socket !== socket) return;
      for (const message of this.pending.splice(0)) socket.send(message);
    };
    socket.onmessage = event => this.receive(event.data);
    socket.onclose = () => {
      if (this.active && this.socket === socket) {
        this.schedule(() => this.connect());
      }
    };
  }
  private receive(raw: string) {
    let event: SocketEvent;
    try {
      event = JSON.parse(raw);
      if (!Number.isInteger(event.sequence) ||
          !['chunk', 'utterance', 'state', 'metric', 'error'].includes(event.kind)) {
        throw new Error('invalid event envelope');
      }
    } catch (reason) {
      this.callbacks.error(
        reason instanceof Error ? reason : new Error(String(reason))
      );
      return;
    }
    if (event.sequence <= this.lastSequence) return;
    if (event.sequence !== this.lastSequence + 1) {
      this.callbacks.error(new Error(
        `sequence gap: expected ${this.lastSequence + 1}, got ${event.sequence}`
      ));
      return;
    }
    this.lastSequence = event.sequence;
    if (event.kind === 'error') {
      const message = (event.payload as { message?: string })?.message;
      this.callbacks.error(new Error(message || 'runtime error'));
    } else {
      this.callbacks[event.kind](event);
    }
  }
  private send(message: object) {
    if (!this.socket || !this.active || this.socket.readyState > 1) {
      throw new Error('session socket is not active');
    }
    const encoded = JSON.stringify(message);
    if (this.socket.readyState === 0) this.pending.push(encoded);
    else this.socket.send(encoded);
  }
  sendUserEvent(payload: { text: string; target?: string }) {
    this.send({ kind: 'user', payload });
  }
  cancel() {
    this.send({ kind: 'cancel' });
  }
  sendPersonaUpdate(payload: object) {
    this.send(payload);
  }
  close() {
    this.active = false;
    this.socket?.close();
  }
}
