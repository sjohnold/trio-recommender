import { describe, expect, it, vi } from 'vitest';
import preset from '../../../data/presets/default-trio.json';
import {
  applyOptimistic, type PersonaUpdateEvent
} from './LivePersonaPanel.svelte';
import type { PersonaConfig } from './api';
const persona = structuredClone(preset.personas[0]) as PersonaConfig;
describe('LivePersonaPanel', () => {
  it('creates a versioned event effective on the next utterance', async () => {
    const send = vi.fn(async (_event: PersonaUpdateEvent) => {});
    const set = vi.fn();
    const next = { ...persona, stats: { ...persona.stats, energy: 6 } };
    const event = await applyOptimistic(persona, 3, next, send, set);
    expect(event).toMatchObject({
      kind: 'persona_update', version: 4, effective_from: 'next_utterance'
    });
    expect(set).toHaveBeenCalledWith(next, 4);
  });
  it('rolls optimistic state back after backend rejection', async () => {
    const next = { ...persona, alignment: 'neutral_good' as const };
    const transitions: [PersonaConfig, number][] = [];
    await expect(applyOptimistic(
      persona, 7, next, async () => { throw new Error('backend rejected'); },
      (value, version) => transitions.push([value, version])
    )).rejects.toThrow('backend rejected');
    expect(transitions).toEqual([[next, 8], [persona, 7]]);
  });
  it('rejects an invalid pool before optimistic mutation', async () => {
    const invalid = {
      ...persona,
      stats: Object.fromEntries(
        Object.keys(persona.stats).map(key => [key, 10])
      ) as PersonaConfig['stats']
    };
    const set = vi.fn();
    await expect(applyOptimistic(persona, 1, invalid, vi.fn(), set))
      .rejects.toThrow('Point budget');
    expect(set).not.toHaveBeenCalled();
  });
});
