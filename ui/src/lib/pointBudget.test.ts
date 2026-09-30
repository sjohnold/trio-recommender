import { describe, expect, it } from 'vitest';
import type { PersonaStats } from './api';
import {
  BUDGET_EXPLANATION, canSet, remainingBonus, usedBonus
} from './pointBudget';

const stats = (value = 5): PersonaStats => ({
  energy: value,
  openness: value,
  nerve: value,
  sharpness: value,
  reasoning: value,
  provocation: value,
  attunement: value
});

describe('point budget', () => {
  it('matches the backend one-way calculation', () => {
    const values = stats(1);
    values.energy = 10;
    values.openness = 8;
    expect(usedBonus(values)).toBe(8);
    expect(remainingBonus(values)).toBe(2);
    expect(BUDGET_EXPLANATION).toContain('ниже 5');
  });

  it('blocks the eleventh point and invalid boundaries', () => {
    const values = stats();
    values.energy = 10;
    values.openness = 10;
    expect(canSet(values, 'nerve', 6)).toBe(false);
    expect(canSet(values, 'nerve', 5)).toBe(true);
    for (const invalid of [0, 11, 5.5, Number.NaN]) {
      expect(canSet(values, 'nerve', invalid)).toBe(false);
    }
  });

  it('cannot make all seven stats maximal', () => {
    const values = stats(10);
    expect(usedBonus(values)).toBe(35);
    expect(remainingBonus(values)).toBe(0);
    expect(canSet({ ...values, energy: 5 }, 'energy', 10)).toBe(false);
  });
});
