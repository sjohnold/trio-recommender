import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compile } from 'svelte/compiler';
const source = readFileSync(
  new URL('./SessionSetup.svelte', import.meta.url), 'utf8'
);
describe('SessionSetup', () => {
  it('compiles with Base, both modes, models and language locks', () => {
    expect(() => compile(source, { generate: 'client' })).not.toThrow();
    expect(source).toContain('Base · 8 GiB · ctx 4096');
    expect(source).toContain("mode: 'A'");
    expect(source).toContain("mode: 'B'");
    expect(source).toContain('State Model');
    for (const language of ['value="ru"', 'value="en"', 'value="sr"']) {
      expect(source).toContain(language);
    }
    expect(source).toContain('Ekavian');
    expect(source).toContain('Ijekavian');
  });
  it('shows State memory and does not promise latency', () => {
    expect(source).toContain('State Model {gib(admission.stateBytes)}');
    expect(source).toContain('only after a local benchmark');
    expect(source).toContain('different model families');
  });
  it('keeps start disabled until every gate passes', () => {
    expect(source).toContain('admission.admitted');
    expect(source).toContain('admission.familiesDistinct');
    expect(source).toContain('disabled={!ready}');
    expect(source).toContain("dispatch('start', value)");
  });
});
