import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compile } from 'svelte/compiler';

const source = readFileSync(
  new URL('./CharacterCard.svelte', import.meta.url),
  'utf8'
);

describe('CharacterCard', () => {
  it('is valid Svelte and exposes all seven controls', () => {
    expect(() => compile(source, { generate: 'client' })).not.toThrow();
    for (const stat of [
      'energy', 'openness', 'nerve', 'attunement',
      'provocation', 'sharpness', 'reasoning'
    ]) {
      expect(source).toContain(`key: '${stat}'`);
    }
  });

  it('uses labelled native keyboard controls with visible values and steppers', () => {
    expect(source).toContain('type="range"');
    expect(source).toContain('min="1"');
    expect(source).toContain('max="10"');
    expect(source).toContain('<label for=');
    expect(source).toContain('<output for=');
    expect(source).toContain('{persona.stats[control.key]}');
    expect(source).toContain('Увеличить ${control.label}');
  });

  it('enforces the point pool, emits immutable changes and keeps the caveat', () => {
    expect(source).toContain("dispatch('change'");
    expect(source).toContain('canSet(persona.stats');
    expect(source).toContain('СВОБОДНЫЕ ОЧКИ');
    expect(source).toContain('не психометрическая оценка');
  });
});
