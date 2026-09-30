<script module lang="ts">
  import type { PersonaConfig } from './api';

  export interface TrioPreset {
    version: '1.0.0';
    personas: [PersonaConfig, PersonaConfig, PersonaConfig];
  }
  export interface StoredPreset extends TrioPreset {
    id: string;
    revision: number;
  }
  export interface SavePresetRequest {
    id: string;
    preset: TrioPreset;
  }
  const roles = ['pragmatist', 'logician', 'empath'];
  const alignments = [
    'lawful_good', 'lawful_neutral', 'lawful_evil',
    'neutral_good', 'true_neutral', 'neutral_evil',
    'chaotic_good', 'chaotic_neutral', 'chaotic_evil'
  ];
  const stats = [
    'energy', 'openness', 'nerve', 'attunement',
    'provocation', 'sharpness', 'reasoning'
  ];
  const exact = (value: object, keys: string[]) =>
    Object.keys(value).sort().join() === [...keys].sort().join();

  export function parsePreset(text: string): TrioPreset {
    const data = JSON.parse(text);
    if (!data || typeof data !== 'object' ||
        !exact(data, ['version', 'personas']) || data.version !== '1.0.0' ||
        !Array.isArray(data.personas) || data.personas.length !== 3) {
      throw new Error('Preset schema must contain version 1.0.0 and three personas');
    }
    const seen = new Set();
    for (const persona of data.personas) {
      if (!persona || !exact(persona, ['name', 'role', 'alignment', 'stats']) ||
          typeof persona.name !== 'string' || !persona.name.trim() ||
          persona.name.length > 64 || !roles.includes(persona.role) ||
          !alignments.includes(persona.alignment) ||
          !persona.stats || !exact(persona.stats, stats)) {
        throw new Error('Persona does not match schema');
      }
      if (seen.has(persona.role)) throw new Error('Persona roles must be unique');
      seen.add(persona.role);
      const values = Object.values(persona.stats) as number[];
      if (values.some(value => !Number.isInteger(value) || value < 1 || value > 10)) {
        throw new Error('Stats must be integers from 1 to 10');
      }
      const used = values.reduce((sum, value) => sum + Math.max(value - 5, 0), 0);
      if (used > 10) throw new Error(`Point budget exceeded: ${used}/10`);
    }
    return data as TrioPreset;
  }
</script>

<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import defaultPreset from '../../../data/presets/default-trio.json';
  import type { PersonaConfig } from './api';

  let {
    personas, saved = []
  }: {
    personas: PersonaConfig[];
    saved?: StoredPreset[];
  } = $props();
  let error = $state('');
  let presetName = $state('my-trio');
  let selected = $state('');
  const dispatch = createEventDispatcher<{
    change: PersonaConfig[];
    save: SavePresetRequest;
  }>();
  const preset = (): TrioPreset => ({
    version: '1.0.0',
    personas: JSON.parse(JSON.stringify(personas)) as PersonaConfig[]
  } as TrioPreset);

  function apply(candidate: TrioPreset) {
    error = '';
    dispatch('change', structuredClone(candidate.personas));
  }
  async function upload(event: Event) {
    const file = (event.currentTarget as HTMLInputElement).files?.[0];
    if (!file) return;
    try { apply(parsePreset(await file.text())); }
    catch (reason) { error = reason instanceof Error ? reason.message : String(reason); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob(
      [JSON.stringify(preset(), null, 2)], { type: 'application/json' }
    ));
    const anchor = Object.assign(document.createElement('a'), {
      href: url, download: 'trio-preset.json'
    });
    anchor.click();
    URL.revokeObjectURL(url);
  }
  function loadSaved() {
    const candidate = saved.find(item => item.id === selected);
    if (!candidate) {
      error = 'Choose a saved preset';
      return;
    }
    apply(parsePreset(JSON.stringify({
      version: candidate.version,
      personas: candidate.personas
    })));
    presetName = candidate.id;
  }
</script>

<section aria-labelledby="preset-title">
  <h3 id="preset-title">Presets</h3>
  <button onclick={() => apply(parsePreset(JSON.stringify(defaultPreset)))}>
    Load default
  </button>
  <label>Import JSON <input type="file" accept="application/json,.json" onchange={upload} /></label>
  <button onclick={download}>Export JSON</button>
  <label class="visible">Saved presets
    <select bind:value={selected}>
      <option value="">Choose preset</option>
      {#each saved as item}
        <option value={item.id}>{item.id} · r{item.revision}</option>
      {/each}
    </select>
  </label>
  <button disabled={!selected} onclick={loadSaved}>Load saved</button>
  <label class="visible">Preset name
    <input class="name" bind:value={presetName} maxlength="64" />
  </label>
  <button
    class="primary"
    disabled={!presetName.trim()}
    onclick={() => dispatch('save', { id: presetName.trim(), preset: preset() })}
  >Save to local server</button>
  {#if error}<p class="error" role="alert">{error}. Current form was not changed.</p>{/if}
</section>

<style>
  section { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; border: 1px solid #504b42; padding: 14px; }
  h3 { margin: 0 auto 0 0; font: 20px Georgia, serif; }
  button, label { border: 1px solid #504b42; background: #191714; color: #eee9de; padding: 8px 11px; font-size: 12px; }
  label { cursor: pointer; } input { display: none; }
  label.visible { display: grid; gap: 4px; padding: 0; border: 0; color: #aaa398; }
  label.visible input, select {
    display: block; min-width: 150px; padding: 7px;
    border: 1px solid #504b42; background: #11100e; color: #eee9de;
  }
  button:disabled { opacity: .4; cursor: default; }
  .primary { border-color: #c9a86a; }
  .error { color: #e99b83; font-size: 12px; }
</style>
