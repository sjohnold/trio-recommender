<script module lang="ts">
  import type { SetupConfig } from './SessionSetup.svelte';
  export interface SwitchGate {
    admitted: boolean; resident: boolean; reason: string;
  }
  export interface BoundaryEvent {
    kind: 'session_boundary'; from: SetupConfig; to: SetupConfig;
    keep_models_loaded: true;
  }
  export function createBoundaryEvent(
    current: SetupConfig, next: SetupConfig,
    gate: SwitchGate, streaming: boolean
  ): BoundaryEvent {
    if (streaming) throw new Error('Finish or stop streaming before switching');
    if (!gate.admitted || !gate.resident) throw new Error(gate.reason);
    if (current.mode === next.mode && current.language === next.language &&
        current.script === next.script && current.variant === next.variant) {
      throw new Error('Language and mode are unchanged');
    }
    return {
      kind: 'session_boundary',
      from: structuredClone(current),
      to: structuredClone(next),
      keep_models_loaded: true
    };
  }
</script>
<script lang="ts">
  import { createEventDispatcher, untrack } from 'svelte';
  import type { SetupConfig } from './SessionSetup.svelte';
  let { current, gate, streaming }: {
    current: SetupConfig;
    gate: SwitchGate;
    streaming: boolean;
  } = $props();
  let mode = $state(untrack(() => current.mode));
  let language = $state(untrack(() => current.language));
  const dispatch = createEventDispatcher<{ boundary: BoundaryEvent }>();
  const changed = $derived(mode !== current.mode || language !== current.language);
  const blocked = $derived(streaming || !gate.admitted || !gate.resident);
  function next(): SetupConfig {
    return {
      ...current, mode, language,
      script: language === 'ru' ? 'Cyrl' : 'Latn',
      variant: language === 'sr' ? 'ekavian' : null
    };
  }
  function switchSegment() {
    dispatch('boundary', createBoundaryEvent(current, next(), gate, streaming));
  }
</script>
<section aria-labelledby="switch-title">
  <div>
    <span>SESSION BOUNDARY</span>
    <h3 id="switch-title">Switch language or runtime mode</h3>
  </div>
  <label>Mode
    <select bind:value={mode} disabled={streaming}>
      <option value="A">Mode A · Trio</option>
      <option value="B">Mode B · one actor</option>
    </select>
  </label>
  <label>Language
    <select bind:value={language} disabled={streaming}>
      <option value="ru">RU</option><option value="en">EN</option><option value="sr">SR</option>
    </select>
  </label>
  <button disabled={blocked || !changed} onclick={switchSegment}>
    Create new segment
  </button>
  {#if streaming}
    <p role="status">Instant switch is blocked while streaming. Stop or wait for completion.</p>
  {:else if !gate.admitted || !gate.resident}
    <p role="status">Gate blocked: {gate.reason}</p>
  {:else}
    <p>Models remain resident; no hidden unload occurs at the boundary.</p>
  {/if}
</section>

<style>
  section { display: grid; grid-template-columns: 1fr auto auto auto; gap: 12px; align-items: end; border: 1px solid #504b42; padding: 15px; }
  span { color: #c9a86a; font: 10px monospace; }
  h3 { margin: 4px 0 0; font: 20px Georgia, serif; }
  label { display: grid; gap: 4px; color: #aaa398; font-size: 11px; }
  select, button { padding: 8px; background: #191714; color: #eee9de; border: 1px solid #504b42; }
  button:disabled { opacity: .4; }
  p { grid-column: 1 / -1; margin: 0; color: #aaa398; font-size: 11px; }
</style>
