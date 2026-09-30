<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { PersonaConfig, PersonaStats, Role } from './api';
  import {
    BONUS_POOL, BUDGET_EXPLANATION, canSet, remainingBonus, usedBonus
  } from './pointBudget';

  let { persona }: { persona: PersonaConfig } = $props();
  const dispatch = createEventDispatcher<{ change: PersonaConfig }>();
  const identities: Record<Role, {
    title: string;
    credo: string;
    avatar: string;
    accent: string;
  }> = {
    pragmatist: {
      title: 'Прагматик',
      credo: '38 лет · бывшая руководительница запусков · мать Лиды',
      avatar: '/avatars/vector.png',
      accent: '#d47a3a'
    },
    logician: {
      title: 'Логик',
      credo: '43 года · редактор математических текстов · ухаживает за отцом',
      avatar: '/avatars/axiom.png',
      accent: '#4da6a8'
    },
    empath: {
      title: 'Эмпат',
      credo: '35 лет · из Нови-Сада · ушла из медиации после провального мира',
      avatar: '/avatars/resonance.png',
      accent: '#a875c2'
    }
  };
  const controls: {
    key: keyof PersonaStats;
    label: string;
    low: string;
    high: string;
  }[] = [
    { key: 'energy', label: 'Энергия', low: 'тихо', high: 'напористо' },
    { key: 'openness', label: 'Открытость', low: 'одна рамка', high: 'альтернативы' },
    { key: 'nerve', label: 'Самообладание', low: 'осторожно', high: 'стойко' },
    { key: 'attunement', label: 'Чуткость', low: 'автономно', high: 'слышит других' },
    { key: 'provocation', label: 'Провокация', low: 'не обостряет', high: 'давит на слабое' },
    { key: 'sharpness', label: 'Резкость', low: 'мягко', high: 'колко / грубо' },
    { key: 'reasoning', label: 'Мышление', low: 'образы', high: 'логическая цепь' }
  ];
  const identity = $derived(identities[persona.role]);
  const used = $derived(usedBonus(persona.stats));
  const remaining = $derived(remainingBonus(persona.stats));

  function update(key: keyof PersonaStats, value: number) {
    if (!canSet(persona.stats, key, value)) return;
    dispatch('change', {
      ...persona,
      stats: { ...persona.stats, [key]: value }
    });
  }

  function step(key: keyof PersonaStats, delta: number) {
    update(key, persona.stats[key] + delta);
  }

  function tagFor(key: keyof PersonaStats, value: number): string | null {
    const labels: Record<keyof PersonaStats, [string, string]> = {
      energy: ['Сдержанный', 'Инициативный'],
      openness: ['Упрямый', 'Гибкий'],
      nerve: ['Осторожный', 'Невозмутимый'],
      attunement: ['Отстранённый', 'Внимательный'],
      provocation: ['Мирный', 'Задиристый'],
      sharpness: ['Мягкий', 'Резкий'],
      reasoning: ['Образный', 'Аналитичный']
    };
    if (value <= 3) return labels[key][0];
    if (value >= 8) return labels[key][1];
    return null;
  }
</script>

<article
  aria-labelledby={`${persona.role}-name`}
  style={`--accent: ${identity.accent}`}
>
  <header class="identity">
    <img src={identity.avatar} alt="" />
    <div>
      <span class="class-label">{identity.title}</span>
      <h3 id={`${persona.role}-name`}>{persona.name}</h3>
      <p>{identity.credo}</p>
    </div>
    <div class="level">Ур. 1</div>
  </header>

  <div class="tags" aria-label="Сильные особенности">
    {#each controls as control}
      {@const tag = tagFor(control.key, persona.stats[control.key])}
      {#if tag}<span>{tag}</span>{/if}
    {/each}
  </div>

  <section class="budget" aria-label="Очки характеристик">
    <div class="budget-copy">
      <span>СВОБОДНЫЕ ОЧКИ</span>
      <strong class:empty={remaining === 0}>{remaining}</strong>
      <small>{used} / {BONUS_POOL} потрачено</small>
    </div>
    <div class="pips" aria-hidden="true">
      {#each Array(BONUS_POOL) as _, index}
        <i class:spent={index < used}></i>
      {/each}
    </div>
    <p>{BUDGET_EXPLANATION}</p>
  </section>

  <div class="controls">
    {#each controls as control}
      <div class="control">
        <div class="stat-line">
          <label for={`${persona.role}-${control.key}`}>{control.label}</label>
          <div class="stepper">
            <button
              type="button"
              aria-label={`Уменьшить ${control.label}`}
              disabled={persona.stats[control.key] <= 1}
              onclick={() => step(control.key, -1)}
            >−</button>
            <output for={`${persona.role}-${control.key}`}>
              {persona.stats[control.key]}
            </output>
            <button
              type="button"
              aria-label={`Увеличить ${control.label}`}
              disabled={!canSet(
                persona.stats, control.key, persona.stats[control.key] + 1
              )}
              onclick={() => step(control.key, 1)}
            >+</button>
          </div>
        </div>
        <input
          id={`${persona.role}-${control.key}`}
          aria-label={control.label}
          type="range"
          min="1"
          max="10"
          step="1"
          value={persona.stats[control.key]}
          oninput={(event) => update(
            control.key,
            Number(event.currentTarget.value)
          )}
        />
        <div class="scale"><span>{control.low}</span><span>{control.high}</span></div>
      </div>
    {/each}
  </div>
  <p class="caveat">
    Это художественные параметры реплик, а не психометрическая оценка человека.
  </p>
</article>

<style>
  article {
    overflow: hidden;
    border: 1px solid #49453f;
    border-top: 3px solid var(--accent);
    background: linear-gradient(145deg, #1c1a17, #151412);
    box-shadow: 0 18px 45px #0005;
  }
  .identity {
    display: grid;
    grid-template-columns: 84px 1fr auto;
    gap: 16px;
    align-items: center;
    padding: 18px;
    background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 13%, transparent), transparent);
    border-bottom: 1px solid #38342e;
  }
  .identity img {
    width: 84px;
    aspect-ratio: 1;
    border: 2px solid var(--accent);
    border-radius: 6px;
    object-fit: cover;
    box-shadow: 0 0 0 4px #111;
  }
  .class-label {
    color: var(--accent);
    font: 700 10px/1 monospace;
    letter-spacing: .14em;
    text-transform: uppercase;
  }
  h3 { margin: 5px 0 4px; font: 29px/1 Georgia, serif; }
  .identity p { margin: 0; color: #aaa398; font-size: 12px; line-height: 1.4; }
  .level {
    align-self: start;
    border: 1px solid #504b42;
    padding: 5px 7px;
    color: #8e887e;
    font: 9px monospace;
    text-transform: uppercase;
  }
  .tags { min-height: 35px; display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 18px 4px; }
  .tags span {
    border: 1px solid color-mix(in srgb, var(--accent) 45%, #38342e);
    padding: 4px 7px;
    color: #d8d1c5;
    background: color-mix(in srgb, var(--accent) 8%, transparent);
    font-size: 10px;
  }
  .budget { margin: 12px 18px 4px; border: 1px solid #504b42; background: #11100e; padding: 12px; }
  .budget-copy { display: flex; align-items: baseline; gap: 9px; }
  .budget-copy span { color: #aaa398; font: 10px monospace; letter-spacing: .08em; }
  .budget-copy strong { color: #f2cf78; font: 24px Georgia, serif; }
  .budget-copy strong.empty { color: #d27c67; }
  .budget-copy small { margin-left: auto; color: #756f66; font: 10px monospace; }
  .pips { display: grid; grid-template-columns: repeat(10, 1fr); gap: 4px; margin-top: 7px; }
  .pips i { height: 5px; background: #302d29; }
  .pips i.spent { background: var(--accent); box-shadow: 0 0 7px color-mix(in srgb, var(--accent) 40%, transparent); }
  .budget p { margin: 8px 0 0; color: #756f66; font-size: 10px; }
  .controls { display: grid; gap: 0; padding: 10px 18px 14px; }
  .control { padding: 9px 0; border-bottom: 1px solid #302d29; }
  .stat-line { display: flex; justify-content: space-between; align-items: center; }
  label { font-size: 12px; font-weight: 700; }
  .stepper { display: grid; grid-template-columns: 26px 30px 26px; align-items: center; text-align: center; }
  .stepper button {
    height: 24px;
    border: 1px solid #504b42;
    background: #24211d;
    color: #d8d1c5;
    font-size: 16px;
    line-height: 1;
  }
  .stepper button:hover:not(:disabled) { border-color: var(--accent); color: #fff; }
  .stepper button:disabled { opacity: .25; cursor: not-allowed; }
  output { color: #f1dec1; font: 700 14px monospace; }
  input { width: 100%; height: 14px; accent-color: var(--accent); }
  .scale { display: flex; justify-content: space-between; color: #716b63; font-size: 9px; }
  .caveat { margin: 0; padding: 0 18px 16px; color: #716b63; font-size: 10px; line-height: 1.4; }
  @media (max-width: 520px) {
    .identity { grid-template-columns: 68px 1fr; }
    .identity img { width: 68px; }
    .level { display: none; }
  }
</style>
