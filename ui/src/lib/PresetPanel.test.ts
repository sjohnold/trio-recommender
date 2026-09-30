import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import preset from '../../../data/presets/default-trio.json';
import { parsePreset } from './PresetPanel.svelte';

describe('PresetPanel', () => {
  it('round-trips all three persona sheets', () => {
    const parsed = parsePreset(JSON.stringify(preset));
    expect(parsed.personas).toHaveLength(3);
    expect(JSON.parse(JSON.stringify(parsed))).toEqual(preset);
  });

  it('rejects schema and point-budget errors before returning state', () => {
    expect(() => parsePreset('{"version":"1.0.0","personas":[]}'))
      .toThrow(/three personas/);
    const invalid = structuredClone(preset);
    for (const key of Object.keys(invalid.personas[0].stats)) {
      invalid.personas[0].stats[key as keyof typeof invalid.personas[0]['stats']] = 10;
    }
    expect(() => parsePreset(JSON.stringify(invalid))).toThrow(/budget/);
  });

  it('keeps local import/export separate from explicit server save', () => {
    const source = readFileSync(
      new URL('./PresetPanel.svelte', import.meta.url), 'utf8'
    );
    expect(source).toContain('type="file"');
    expect(source).toContain('URL.createObjectURL');
    expect(source).toContain("dispatch('save'");
    expect(source).toContain('Load saved');
    expect(source).toContain('Preset name');
    expect(source).toContain('Current form was not changed');
  });
});
