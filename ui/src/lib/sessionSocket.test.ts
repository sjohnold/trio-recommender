import { describe, expect, it, vi } from 'vitest';
import { SessionSocket, type SessionCallbacks } from './sessionSocket';
class FakeSocket {
  readyState = 1; onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  send(data: string) { this.sent.push(data); }
  close() { this.onclose?.(); }
  emit(value: object) { this.onmessage?.({ data: JSON.stringify(value) }); }
}
const callbacks = (): SessionCallbacks => ({
  chunk: vi.fn(), utterance: vi.fn(), state: vi.fn(),
  metric: vi.fn(), error: vi.fn()
});
describe('SessionSocket', () => {
  it('rejects external URLs and sends typed user events', () => {
    expect(() => new SessionSocket('wss://evil.test', callbacks()))
      .toThrow(/same-origin/);
    const socket = new FakeSocket();
    const client = new SessionSocket('/ws/s', callbacks(), () => socket);
    client.sendUserEvent({ text: 'hello', target: 'logician' });
    expect(JSON.parse(socket.sent[0])).toEqual({
      kind: 'user', payload: { text: 'hello', target: 'logician' }
    });
  });
  it('ignores duplicate/out-of-order chunks', () => {
    const cb = callbacks();
    const socket = new FakeSocket();
    new SessionSocket('/ws/s', cb, () => socket);
    socket.emit({ sequence: 1, kind: 'chunk', payload: { text: 'A' } });
    socket.emit({ sequence: 1, kind: 'chunk', payload: { text: 'A' } });
    socket.emit({ sequence: 3, kind: 'chunk', payload: { text: 'C' } });
    expect(cb.chunk).toHaveBeenCalledTimes(1);
    expect(cb.error).toHaveBeenCalledWith(expect.objectContaining({
      message: 'sequence gap: expected 2, got 3'
    }));
  });
  it('keeps a multi-turn session active after a terminal utterance', () => {
    const sockets: FakeSocket[] = [];
    const client = new SessionSocket('/ws/s', callbacks(), () => {
      const socket = new FakeSocket(); sockets.push(socket); return socket;
    }, callback => callback());
    sockets[0].close();
    expect(sockets).toHaveLength(2);
    sockets[1].emit({
      sequence: 1, kind: 'utterance', payload: { state: 'COMPLETED' }
    });
    sockets[1].close();
    expect(sockets).toHaveLength(3);
    client.close();
  });
});
