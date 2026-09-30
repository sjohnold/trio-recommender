import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compile } from 'svelte/compiler';
import { metricText, passText, rateText } from './MetricsPanel.svelte';

describe('MetricsPanel', () => {
  it('renders null and target states honestly in text', () => {
    expect(metricText(null)).toBe('Insufficient data');
    expect(metricText(12.345, ' ms')).toBe('12.35 ms');
    expect(passText(null)).toBe('NOT EVALUATED');
    expect(passText(false)).toBe('FAIL');
    expect(passText(true)).toBe('PASS');
    expect(rateText(.125)).toBe('12.50%');
  });

  it('shows all runtime, drift, integrity and fallback signals', () => {
    const source = readFileSync(
      new URL('./MetricsPanel.svelte', import.meta.url), 'utf8'
    );
    expect(() => compile(source, { generate: 'client' })).not.toThrow();
    for (const label of [
      'TTFT', 'Full generation', 'Round', 'Personality drift',
      'Worldview drift', 'Language integrity', 'Timeouts', 'State fallback'
    ]) {
      expect(source).toContain(label);
    }
    expect(source).toContain('Runtime errors');
  });

  it('binds every display to one explicit language/mode bucket', () => {
    const source = readFileSync(
      new URL('./MetricsPanel.svelte', import.meta.url), 'utf8'
    );
    expect(source).toContain('bucket.language.toUpperCase()');
    expect(source).toContain('MODE {bucket.mode}');
    expect(source).toContain('Exact language/mode bucket');
    expect(source).not.toContain('averageLanguages');
  });
});
