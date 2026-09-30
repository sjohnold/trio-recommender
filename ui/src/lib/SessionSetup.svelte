<script module lang="ts">
  export interface SetupConfig {
    profile: 'Base';
    mode: 'A' | 'B';
    actorModels: string[];
    stateModel: string;
    language: 'ru' | 'en' | 'sr';
    script: 'Latn' | 'Cyrl';
    variant: 'ekavian' | 'ijekavian' | null;
  }
  export interface AdmissionPreview {
    admitted: boolean;
    reason: string;
    actorBytes: number;
    stateBytes: number;
    reserveBytes: number;
    budgetBytes: number;
    familiesDistinct: boolean;
  }
</script>
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  let { value, admission, models = [] }: {
    value: SetupConfig;
    admission: AdmissionPreview;
    models?: string[];
  } = $props();
  const dispatch = createEventDispatcher<{
    change: SetupConfig;
    start: SetupConfig;
  }>();
  const gib = (bytes: number) => `${(bytes / 1024 ** 3).toFixed(2)} GiB`;
  const ready = $derived(
    admission.admitted &&
    value.stateModel.trim().length > 0 &&
    value.actorModels.length === (value.mode === 'A' ? 3 : 1) &&
    value.actorModels.every(Boolean) &&
    (value.mode === 'B' || admission.familiesDistinct)
  );
  function change(patch: Partial<SetupConfig>) {
    dispatch('change', { ...value, ...patch });
  }
  function setLanguage(language: SetupConfig['language']) {
    change(language === 'sr'
      ? { language, script: 'Latn', variant: 'ekavian' }
      : { language, script: language === 'ru' ? 'Cyrl' : 'Latn', variant: null });
  }
  function setActor(index: number, model: string) {
    const actorModels = [...value.actorModels];
    actorModels[index] = model;
    change({ actorModels });
  }
</script>
<section aria-labelledby="setup-title">
  <h3 id="setup-title">Session setup</h3>
  <div class="fields">
    <label>Profile
      <select disabled><option selected>Base · 8 GiB · ctx 4096</option></select>
    </label>
    <fieldset>
      <legend>Runtime mode</legend>
      <label><input type="radio" name="mode" value="A" checked={value.mode === 'A'}
        onchange={() => change({ mode: 'A', actorModels: ['', '', ''] })} /> Mode A · Trio</label>
      <label><input type="radio" name="mode" value="B" checked={value.mode === 'B'}
        onchange={() => change({ mode: 'B', actorModels: [''] })} /> Mode B · one actor</label>
    </fieldset>
    {#each value.actorModels as model, index}
      <label>Actor model {index + 1}
        {#if models.length}
          <select value={model} onchange={(event) => setActor(index, event.currentTarget.value)}>
            <option value="">Choose a local model</option>
            {#each models as name}<option value={name}>{name}</option>{/each}
          </select>
        {:else}
          <input value={model} oninput={(event) => setActor(index, event.currentTarget.value)} />
        {/if}
      </label>
    {/each}
    {#if value.mode === 'A'}
      <p class:failed={!admission.familiesDistinct}>Mode A requires three different model families.</p>
    {/if}
    <label>State Model
      {#if models.length}
        <select value={value.stateModel}
          onchange={(event) => change({ stateModel: event.currentTarget.value })}>
          <option value="">Choose a local model</option>
          {#each models as name}<option value={name}>{name}</option>{/each}
        </select>
      {:else}
        <input value={value.stateModel}
          oninput={(event) => change({ stateModel: event.currentTarget.value })} />
      {/if}
    </label>
    <label>Language
      <select value={value.language}
        onchange={(event) => setLanguage(event.currentTarget.value as SetupConfig['language'])}>
        <option value="ru">RU</option><option value="en">EN</option><option value="sr">SR</option>
      </select>
    </label>
    {#if value.language === 'sr'}
      <label>Script
        <select value={value.script}
          onchange={(event) => change({ script: event.currentTarget.value as 'Latn' | 'Cyrl' })}>
          <option value="Latn">Latin</option><option value="Cyrl">Cyrillic</option>
        </select>
      </label>
      <label>Variant
        <select value={value.variant ?? 'ekavian'}
          onchange={(event) => change({ variant: event.currentTarget.value as 'ekavian' | 'ijekavian' })}>
          <option value="ekavian">Ekavian</option><option value="ijekavian">Ijekavian</option>
        </select>
      </label>
    {/if}
  </div>
  <aside class:failed={!admission.admitted}>
    <strong>Admission: {admission.admitted ? 'PASS' : 'BLOCKED'}</strong>
    <span>Actors {gib(admission.actorBytes)}</span>
    <span>State Model {gib(admission.stateBytes)}</span>
    <span>Reserve {gib(admission.reserveBytes)} / budget {gib(admission.budgetBytes)}</span>
    <small>{admission.reason}. Latency is reported only after a local benchmark.</small>
  </aside>
  <button disabled={!ready} onclick={() => dispatch('start', value)}>Start local session</button>
</section>

<style>
  section { display: grid; grid-template-columns: 2fr 1fr; gap: 18px; border: 1px solid #504b42; padding: 20px; }
  h3 { grid-column: 1 / -1; margin: 0; font: 24px Georgia, serif; }
  .fields { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  label, aside { display: grid; gap: 5px; color: #aaa398; font-size: 12px; }
  fieldset { border: 1px solid #504b42; } input, select { background: #11100e; color: #eee9de; border: 1px solid #504b42; padding: 7px; }
  aside { align-content: start; border-left: 3px solid #7ca982; padding: 12px; }
  .failed { color: #e99b83; border-color: #c36f58; }
  button { grid-column: 2; padding: 11px; background: #c9a86a; border: 0; }
  button:disabled { opacity: .4; }
</style>
