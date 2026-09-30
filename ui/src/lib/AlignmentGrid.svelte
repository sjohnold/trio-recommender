<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Alignment } from './api';

  let {
    value,
    name = 'alignment'
  }: { value: Alignment; name?: string } = $props();
  const dispatch = createEventDispatcher<{ change: Alignment }>();
  const cells: { value: Alignment; label: string; behavior: string }[] = [
    { value: 'lawful_good', label: 'Законопослушный добрый', behavior: 'Поддерживает и возвращает разговор к делу.' },
    { value: 'lawful_neutral', label: 'Законопослушный нейтральный', behavior: 'Защищает порядок, не выбирая сторону.' },
    { value: 'lawful_evil', label: 'Законопослушный злой', behavior: 'Холодно прижимает слабые доводы к фактам.' },
    { value: 'neutral_good', label: 'Нейтральный добрый', behavior: 'Примиряет, проясняет и снимает лишнее напряжение.' },
    { value: 'true_neutral', label: 'Истинно нейтральный', behavior: 'Наблюдает и не обязан вмешиваться.' },
    { value: 'neutral_evil', label: 'Нейтральный злой', behavior: 'Колко давит на уязвимое место аргумента.' },
    { value: 'chaotic_good', label: 'Хаотичный добрый', behavior: 'Ломает бесполезный порядок ради результата.' },
    { value: 'chaotic_neutral', label: 'Хаотичный нейтральный', behavior: 'Свободно меняет рамку и форму разговора.' },
    { value: 'chaotic_evil', label: 'Хаотичный злой', behavior: 'Едко и резко расшатывает удобные позиции.' }
  ];
</script>

<fieldset>
  <legend>Мировоззрение</legend>
  <div class="axis communion">ДОБРО → ЗЛО · отношение к собеседникам</div>
  <div class="layout">
    <div class="axis order">ПОРЯДОК<br />ЗАКОН<br />↓<br />ХАОС</div>
    <div class="grid">
      {#each cells as cell}
        <label class:active={value === cell.value}>
          <input
            type="radio"
            {name}
            value={cell.value}
            checked={value === cell.value}
            onchange={() => dispatch('change', cell.value)}
          />
          <strong>{cell.label}</strong>
          <small>{cell.behavior}</small>
        </label>
      {/each}
    </div>
  </div>
  <p>
    «Злые» варианты могут быть жёсткими и грубоватыми к доводам, но не разрешают
    унижать человека, угрожать или бить по личным признакам.
  </p>
</fieldset>

<style>
  fieldset { min-width: 0; border: 1px solid #504b42; padding: 18px; }
  legend { padding: 0 8px; font: 22px Georgia, serif; }
  .axis { color: #c9a86a; font: 10px/1.6 monospace; letter-spacing: .08em; }
  .communion { margin: 0 0 8px 68px; text-align: center; }
  .layout { display: grid; grid-template-columns: 58px 1fr; gap: 10px; }
  .order { align-self: center; text-align: center; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
  label { position: relative; min-height: 98px; border: 1px solid #38342e; padding: 10px; cursor: pointer; }
  label.active { border-color: #c9a86a; background: linear-gradient(145deg, #30291e, #211e19); box-shadow: inset 0 0 0 1px #c9a86a33; }
  label:has(input:focus-visible) { outline: 3px solid #e2c487; outline-offset: 2px; }
  input { position: absolute; opacity: 0; }
  strong, small { display: block; }
  strong { margin-bottom: 7px; font-size: 11px; line-height: 1.25; }
  small, p { color: #8e887e; font-size: 10px; line-height: 1.35; }
  p { margin: 14px 0 0 68px; }
</style>
