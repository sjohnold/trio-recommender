<script module lang="ts">
  import type { PersonaConfig } from './api';
  import { usedBonus } from './pointBudget';

  export interface PersonaUpdateEvent {
    kind: 'persona_update'; version: number; persona: PersonaConfig;
    effective_from: 'next_utterance';
  }
  export async function applyOptimistic(
    current: PersonaConfig,
    version: number,
    next: PersonaConfig,
    send: (event: PersonaUpdateEvent) => Promise<void>,
    set: (persona: PersonaConfig, version: number) => void
  ): Promise<PersonaUpdateEvent> {
    if (usedBonus(next.stats) > 10) throw new Error('Point budget exceeded');
    const event: PersonaUpdateEvent = {
      kind: 'persona_update',
      version: version + 1,
      persona: structuredClone(next),
      effective_from: 'next_utterance'
    };
    set(next, event.version);
    try {
      await send(event);
      return event;
    } catch (error) {
      set(current, version);
      throw error;
    }
  }
</script>
<script lang="ts">
  import { untrack } from 'svelte';
  import CharacterCard from './CharacterCard.svelte';
  import AlignmentGrid from './AlignmentGrid.svelte';
  import type { PersonaConfig } from './api';

  interface GenerationSnapshot {
    utteranceId: string; personaVersion: number; stats: PersonaConfig['stats'];
    alignment: PersonaConfig['alignment'];
  }
  let { persona, version, snapshot, sendUpdate }: {
    persona: PersonaConfig;
    version: number;
    snapshot: GenerationSnapshot | null;
    sendUpdate: (event: PersonaUpdateEvent) => Promise<void>;
  } = $props();
  let current = $state(structuredClone(untrack(() => persona)));
  let currentVersion = $state(untrack(() => version));
  let pending = $state(false);
  let error = $state('');
  async function update(next: PersonaConfig) {
    if (pending) return;
    pending = true;
    error = '';
    try {
      await applyOptimistic(
        current, currentVersion, next, sendUpdate,
        (value, nextVersion) => {
          current = structuredClone(value);
          currentVersion = nextVersion;
        }
      );
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    } finally {
      pending = false;
    }
  }
</script>
<section aria-labelledby="live-persona-title" aria-busy={pending}>
  <header>
    <div>
      <span>LIVE PERSONA · VERSION {currentVersion}</span>
      <h3 id="live-persona-title">Applies from the next utterance</h3>
    </div>
    <output>{10 - Math.min(10, usedBonus(current.stats))} bonus points left</output>
  </header>
  <div class="editor" class:pending>
    <CharacterCard persona={current} on:change={(event) => update(event.detail)} />
    <AlignmentGrid
      value={current.alignment}
      name={`${current.role}-live-alignment`}
      on:change={(event) => update({ ...current, alignment: event.detail })}
    />
  </div>
  {#if snapshot}
    <aside>
      <strong>Current streaming snapshot · {snapshot.utteranceId}</strong>
      <span>Persona version {snapshot.personaVersion}</span>
      <code>{JSON.stringify({
        stats: snapshot.stats, alignment: snapshot.alignment
      })}</code>
    </aside>
  {/if}
  {#if error}<p role="alert">{error}. Optimistic change was rolled back.</p>{/if}
</section>

<style>
  section { display: grid; gap: 14px; }
  header { display: flex; justify-content: space-between; align-items: end; }
  header span, output { color: #c9a86a; font: 11px monospace; }
  h3 { margin: 5px 0 0; font: 22px Georgia, serif; }
  .editor { display: grid; grid-template-columns: 1fr 1.4fr; gap: 14px; }
  .editor.pending { opacity: .55; pointer-events: none; }
  aside { display: grid; gap: 5px; border-left: 3px solid #6f91ad; padding: 10px; color: #aaa398; font-size: 11px; }
  code { white-space: pre-wrap; }
  p { color: #e99b83; }
</style>
