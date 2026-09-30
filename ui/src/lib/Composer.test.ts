import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import { compile } from 'svelte/compiler';
import { ComposerController } from './Composer.svelte';

describe('Composer', () => {
  it('sends immediately and marks streaming submit as interrupt', () => {
    const send = vi.fn();
    const callbacks: (() => void)[] = [];
    const controller = new ComposerController(
      send, vi.fn(), callback => callbacks.push(callback)
    );
    expect(controller.submit(' hello ', true)).toBe(true);
    expect(send).toHaveBeenCalledWith({ text: 'hello', interrupt: true });
    expect(callbacks).toHaveLength(1);
  });

  it('deduplicates double submit and ignores empty text', () => {
    const send = vi.fn();
    const callbacks: (() => void)[] = [];
    const controller = new ComposerController(
      send, vi.fn(), callback => callbacks.push(callback)
    );
    expect(controller.submit('same', false)).toBe(true);
    expect(controller.submit(' same ', false)).toBe(false);
    expect(controller.submit('   ', false)).toBe(false);
    expect(send).toHaveBeenCalledTimes(1);
    callbacks[0]();
    expect(controller.submit('same', false)).toBe(true);
  });

  it('Stop emits only cancel and component remains keyboard accessible', () => {
    const send = vi.fn();
    const cancel = vi.fn();
    new ComposerController(send, cancel).stop();
    expect(cancel).toHaveBeenCalledOnce();
    expect(send).not.toHaveBeenCalled();
    const source = readFileSync(
      new URL('./Composer.svelte', import.meta.url), 'utf8'
    );
    expect(() => compile(source, { generate: 'client' })).not.toThrow();
    expect(source).toContain("event.key === 'Enter'");
    expect(source).toContain('Остановить');
  });
});
