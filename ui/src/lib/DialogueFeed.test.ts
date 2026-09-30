import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compile } from 'svelte/compiler';
import {
  applyFeedEvent, type FeedItem
} from './DialogueFeed.svelte';

const event = (sequence: number, kind: 'chunk' | 'utterance', payload: object) =>
  ({ sequence, kind, payload });

describe('DialogueFeed', () => {
  it('appends chunks into one bubble before done', () => {
    let items: FeedItem[] = [];
    items = applyFeedEvent(items, event(1, 'chunk', {
      utterance_id: 'u', role: 'logician', text: 'First '
    }));
    items = applyFeedEvent(items, event(2, 'chunk', {
      utterance_id: 'u', text: 'tokens'
    }));
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      text: 'First tokens', state: 'STREAMING', role: 'logician'
    });
  });

  it('ignores duplicate chunks and does not replace completed text', () => {
    let items = applyFeedEvent([], event(1, 'chunk', {
      utterance_id: 'u', role: 'empath', text: 'partial'
    }));
    const duplicate = applyFeedEvent(items, event(1, 'chunk', {
      utterance_id: 'u', text: 'partial'
    }));
    expect(duplicate).toBe(items);
    items = applyFeedEvent(items, event(2, 'utterance', {
      utterance_id: 'u', state: 'COMPLETED', text: 'replacement'
    }));
    expect(items[0].text).toBe('partial');
    expect(items[0].state).toBe('COMPLETED');
  });

  it('keeps interrupted partial text and renders visible status', () => {
    let items = applyFeedEvent([], event(1, 'chunk', {
      utterance_id: 'u', role: 'pragmatist', text: 'kept'
    }));
    items = applyFeedEvent(items, event(2, 'utterance', {
      utterance_id: 'u', state: 'INTERRUPTED', reason: 'user_interrupt'
    }));
    expect(items[0].text).toBe('kept');
    expect(items[0].reason).toBe('user_interrupt');
    const source = readFileSync(
      new URL('./DialogueFeed.svelte', import.meta.url), 'utf8'
    );
    expect(() => compile(source, { generate: 'client' })).not.toThrow();
    expect(source).toContain("INTERRUPTED: 'остановлено'");
    expect(source).toContain('displayName(item)');
    expect(source).toContain('/avatars/resonance.png');
  });
});
