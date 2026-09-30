import { describe, expect, it } from 'vitest';
import {
  createBoundaryEvent, type SwitchGate
} from './SessionControls.svelte';
import type { SetupConfig } from './SessionSetup.svelte';
const current: SetupConfig = {
  profile: 'Base', mode: 'A', actorModels: ['a', 'b', 'c'],
  stateModel: 'state', language: 'en', script: 'Latn', variant: null
};
const pass: SwitchGate = { admitted: true, resident: true, reason: 'admitted' };
describe('SessionControls', () => {
  it('creates a boundary and explicitly keeps models loaded', () => {
    const next = { ...current, language: 'sr' as const, variant: 'ekavian' as const };
    const event = createBoundaryEvent(current, next, pass, false);
    expect(event.kind).toBe('session_boundary');
    expect(event.keep_models_loaded).toBe(true);
    expect(event.from.language).toBe('en');
    expect(event.to.language).toBe('sr');
  });
  it('blocks switching while streaming', () => {
    const next = { ...current, mode: 'B' as const };
    expect(() => createBoundaryEvent(current, next, pass, true))
      .toThrow(/streaming/);
  });
  it('requires both admission and residency gates', () => {
    const next = { ...current, mode: 'B' as const };
    expect(() => createBoundaryEvent(
      current, next, { admitted: false, resident: true, reason: 'over budget' },
      false
    )).toThrow('over budget');
    expect(() => createBoundaryEvent(
      current, next, { admitted: true, resident: false, reason: 'not resident' },
      false
    )).toThrow('not resident');
  });
  it('does not create a boundary for an unchanged lock', () => {
    expect(() => createBoundaryEvent(current, current, pass, false))
      .toThrow(/unchanged/);
  });
});
