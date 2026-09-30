import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compile } from 'svelte/compiler';

const source = readFileSync(
  new URL('./AlignmentGrid.svelte', import.meta.url), 'utf8'
);
const values = [
  'lawful_good', 'lawful_neutral', 'lawful_evil',
  'neutral_good', 'true_neutral', 'neutral_evil',
  'chaotic_good', 'chaotic_neutral', 'chaotic_evil'
];

describe('AlignmentGrid', () => {
  it('compiles and exposes all stable enum cells', () => {
    expect(() => compile(source, { generate: 'client' })).not.toThrow();
    for (const value of values) {
      expect(source).toContain(`value: '${value}'`);
    }
  });

  it('is a single native keyboard radio group with visible focus', () => {
    expect(source).toContain('type="radio"');
    expect(source).toContain('checked={value === cell.value}');
    expect(source).toContain("dispatch('change', cell.value)");
    expect(source).toContain('input:focus-visible');
    expect(source).toContain('ПОРЯДОК');
    expect(source).toContain('ДОБРО → ЗЛО');
  });

  it('states the scientific and safety boundaries', () => {
    expect(source).toContain('могут быть жёсткими и грубоватыми');
    expect(source).toContain('не разрешают');
    expect(source).toContain('унижать человека');
  });
});
