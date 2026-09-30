import type { PersonaStats } from './api';

export const BONUS_POOL = 10;
export const BUDGET_EXPLANATION =
  'Баллы выше 5 стоят очки развития. Снижение ниже 5 очков не возвращает.';

export function usedBonus(stats: PersonaStats): number {
  return Object.values(stats).reduce(
    (total, value) => total + Math.max(value - 5, 0),
    0
  );
}

export function remainingBonus(stats: PersonaStats): number {
  return Math.max(BONUS_POOL - usedBonus(stats), 0);
}

export function canSet(
  stats: PersonaStats,
  key: keyof PersonaStats,
  value: number
): boolean {
  if (!Number.isInteger(value) || value < 1 || value > 10) return false;
  return usedBonus({ ...stats, [key]: value }) <= BONUS_POOL;
}
