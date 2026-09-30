<script lang="ts">
  import { onMount } from 'svelte';
  import defaultPreset from '../../data/presets/default-trio.json';
  import AlignmentGrid from './lib/AlignmentGrid.svelte';
  import CharacterCard from './lib/CharacterCard.svelte';
  import Composer, { type UserCommand } from './lib/Composer.svelte';
  import DialogueFeed, {
    applyFeedEvent, type FeedItem
  } from './lib/DialogueFeed.svelte';
  import MetricsPanel, { type MetricsBucket } from './lib/MetricsPanel.svelte';
  import PresetPanel, {
    type SavePresetRequest, type StoredPreset
  } from './lib/PresetPanel.svelte';
  import SessionSetup, {
    type AdmissionPreview, type SetupConfig
  } from './lib/SessionSetup.svelte';
  import { api, type PersonaConfig } from './lib/api';
  import {
    SessionSocket, type SocketEvent
  } from './lib/sessionSocket';

  type View = 'characters' | 'session';
  interface ModelInfo {
    name: string;
    digest: string;
    size: number;
    family: string;
    parameter_size: string;
    quantization: string;
  }
  interface SessionCreated { session_id: string; }
  const avatarFor = (role: PersonaConfig['role']) => ({
    pragmatist: '/avatars/vector.png',
    logician: '/avatars/axiom.png',
    empath: '/avatars/resonance.png'
  }[role]);
  const classFor = (role: PersonaConfig['role']) => ({
    pragmatist: 'Прагматик',
    logician: 'Логик',
    empath: 'Эмпат'
  }[role]);

  const route = (): View =>
    location.hash === '#/session' ? 'session' : 'characters';
  const emptyAdmission = (): AdmissionPreview => ({
    admitted: false,
    reason: 'Waiting for the local Ollama model list',
    actorBytes: 0,
    stateBytes: 0,
    reserveBytes: 768 * 1024 ** 2,
    budgetBytes: 8 * 1024 ** 3,
    familiesDistinct: true
  });
  const emptyMetrics = (
    language: SetupConfig['language'] = 'ru',
    mode: SetupConfig['mode'] = 'A'
  ): MetricsBucket => ({
    language, mode,
    ttft: { p50: null, p95: null, targetPass: null },
    full: { p50: null, p95: null, targetPass: null },
    round: { p50: null, p95: null, targetPass: null },
    personalityDrift: null,
    personalityDrifted: null,
    worldviewCell: null,
    worldviewDrifted: null,
    integrityReasons: null,
    timeoutRate: null,
    stateFallbackRate: null,
    errors: []
  });

  let view: View = $state('characters');
  let personas = $state(
    structuredClone(defaultPreset.personas) as PersonaConfig[]
  );
  let models = $state<ModelInfo[]>([]);
  let savedPresets = $state<StoredPreset[]>([]);
  let setup = $state<SetupConfig>({
    profile: 'Base',
    mode: 'A',
    actorModels: ['', '', ''],
    stateModel: '',
    language: 'ru',
    script: 'Cyrl',
    variant: null
  });
  let admission = $state<AdmissionPreview>(emptyAdmission());
  let modelError = $state('');
  let notice = $state('');
  let busy = $state(false);
  let sessionId = $state('');
  let feed = $state<FeedItem[]>([]);
  let streaming = $state(false);
  let metrics = $state<MetricsBucket>(emptyMetrics());
  let socket: SessionSocket | null = null;
  let admissionRequest = 0;

  function navigate(next: View) {
    location.hash = `#/${next}`;
  }

  async function loadModels() {
    modelError = '';
    try {
      models = await api.request<ModelInfo[]>('/api/models');
      if (!models.length) {
        modelError = 'Ollama is running, but no models are installed.';
        admission = { ...emptyAdmission(), reason: modelError };
        return;
      }
      const ordered = [...models].sort((left, right) => left.size - right.size);
      const state = ordered[0]?.name ?? '';
      const actors = modeAActors(models, state);
      setup = { ...setup, mode: 'A', actorModels: actors, stateModel: state };
      await refreshAdmission(setup);
    } catch (reason) {
      modelError = reason instanceof Error ? reason.message : String(reason);
      admission = { ...emptyAdmission(), reason: modelError };
    }
  }

  function modeAActors(items: ModelInfo[], stateModel: string): string[] {
    const chosen: ModelInfo[] = [];
    for (const model of [...items].sort((left, right) => left.size - right.size)) {
      if (
        model.name !== stateModel
        && !chosen.some(candidate => candidate.family === model.family)
      ) {
        chosen.push(model);
      }
      if (chosen.length === 3) break;
    }
    return [
      chosen[0]?.name ?? '',
      chosen[1]?.name ?? '',
      chosen[2]?.name ?? ''
    ];
  }

  async function loadPresets() {
    try {
      savedPresets = await api.request<StoredPreset[]>('/api/presets');
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    }
  }

  async function refreshAdmission(candidate: SetupConfig) {
    const request = ++admissionRequest;
    try {
      const result = await api.request<AdmissionPreview>('/api/admission', {
        method: 'POST',
        body: JSON.stringify({
          profile: candidate.profile,
          mode: candidate.mode,
          actor_models: candidate.actorModels,
          state_model: candidate.stateModel
        })
      });
      if (request === admissionRequest) admission = result;
    } catch (reason) {
      if (request === admissionRequest) {
        admission = {
          ...emptyAdmission(),
          reason: reason instanceof Error ? reason.message : String(reason)
        };
      }
    }
  }

  function updateSetup(candidate: SetupConfig) {
    if (candidate.actorModels.every(model => !model)) {
      candidate = candidate.mode === 'A'
        ? { ...candidate, actorModels: modeAActors(models, candidate.stateModel) }
        : {
            ...candidate,
            actorModels: [models
              .filter(model => model.name !== candidate.stateModel)
              .sort((left, right) => left.size - right.size)[0]?.name ?? '']
          };
    }
    setup = candidate;
    void refreshAdmission(candidate);
  }

  function updatePersona(index: number, persona: PersonaConfig) {
    personas = personas.map((item, position) =>
      position === index ? persona : item
    );
  }

  async function savePreset(request: SavePresetRequest) {
    notice = '';
    try {
      await api.request('/api/presets', {
        method: 'POST',
        body: JSON.stringify(request)
      });
      await loadPresets();
      notice = `Preset "${request.id}" saved to the local SQLite database.`;
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    }
  }

  function snapshot(config: SetupConfig) {
    return {
      mode: config.mode,
      actor_models: config.actorModels,
      state_model: config.stateModel,
      model_digests: Object.fromEntries(
        [...new Set([...config.actorModels, config.stateModel])].map(name => [
          name, models.find(model => model.name === name)?.digest ?? ''
        ])
      ),
      profile: config.profile,
      language_lock: {
        language: config.language,
        script: config.script,
        variant: config.variant
      },
      ablations: { stage1: true, stage2: true, stage3: true },
      seed: 0,
      personas: JSON.parse(JSON.stringify(personas)) as PersonaConfig[]
    };
  }

  function receiveFeed(event: SocketEvent) {
    try {
      feed = applyFeedEvent(feed, event);
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    }
  }

  function connect(id: string) {
    socket?.close();
    socket = new SessionSocket(`/ws/sessions/${id}`, {
      chunk: receiveFeed,
      utterance: event => {
        receiveFeed(event);
        const state = (event.payload as { state?: string }).state;
        if (['COMPLETED', 'INTERRUPTED', 'TIMED_OUT', 'FAILED'].includes(state ?? '')) {
          void refreshMetrics();
        }
      },
      state: event => {
        const phase = (event.payload as { phase?: string }).phase;
        if (phase === 'round_started') streaming = true;
        if (phase === 'round_completed') {
          streaming = false;
          void refreshMetrics();
        }
      },
      metric: () => void refreshMetrics(),
      error: error => {
        streaming = false;
        notice = error.message;
      }
    });
  }

  async function startSession(config: SetupConfig) {
    busy = true;
    notice = '';
    try {
      const result = await api.request<SessionCreated>('/api/sessions', {
        method: 'POST',
        body: JSON.stringify(snapshot(config))
      });
      sessionId = result.session_id;
      feed = [];
      metrics = emptyMetrics(config.language, config.mode);
      connect(sessionId);
      notice = `Local session ${sessionId.slice(0, 8)} is ready.`;
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    } finally {
      busy = false;
    }
  }

  function send(command: UserCommand) {
    try {
      feed = [...feed, {
        utteranceId: `user-${Date.now()}-${feed.length}`,
        role: 'user',
        name: 'Вы',
        text: command.text,
        state: 'COMPLETED',
        lastSequence: 0
      }];
      socket?.sendUserEvent({ text: command.text });
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    }
  }

  function cancel() {
    try {
      socket?.cancel();
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    }
  }

  async function refreshMetrics() {
    if (!sessionId) return;
    try {
      metrics = await api.request<MetricsBucket>(
        `/api/sessions/${sessionId}/metrics`
      );
    } catch (reason) {
      notice = reason instanceof Error ? reason.message : String(reason);
    }
  }

  function resetSession() {
    socket?.close();
    socket = null;
    sessionId = '';
    feed = [];
    streaming = false;
    notice = '';
    metrics = emptyMetrics(setup.language, setup.mode);
  }

  onMount(() => {
    const sync = () => view = route();
    sync();
    addEventListener('hashchange', sync);
    void loadModels();
    void loadPresets();
    return () => {
      removeEventListener('hashchange', sync);
      socket?.close();
    };
  });
</script>

<svelte:head><title>Trio · локальная ролевая дискуссия</title></svelte:head>

<main>
  <header class="masthead">
    <div>
      <span class="eyebrow">ЛОКАЛЬНАЯ РОЛЕВАЯ ДИСКУССИЯ</span>
      <h1>Trio</h1>
    </div>
    <nav aria-label="Primary">
      <button class:active={view === 'characters'} onclick={() => navigate('characters')}>
        Персонажи
      </button>
      <button class:active={view === 'session'} onclick={() => navigate('session')}>
        Дискуссия
      </button>
    </nav>
  </header>

  {#if notice}<p class="notice" role="status">{notice}</p>{/if}

  {#if view === 'characters'}
    <section class="page-heading" aria-labelledby="characters-title">
      <p class="index">01 / ОТРЯД</p>
      <h2 id="characters-title">Соберите троицу</h2>
      <p>Распределите ограниченные очки и задайте каждому собственную манеру спора.</p>
    </section>
    <PresetPanel
      {personas}
      saved={savedPresets}
      on:change={(event) => personas = event.detail}
      on:save={(event) => savePreset(event.detail)}
    />
    <div class="persona-grid">
      {#each personas as persona, index (persona.role)}
        <div class="persona-editor">
          <CharacterCard
            {persona}
            on:change={(event) => updatePersona(index, event.detail)}
          />
          <AlignmentGrid
            value={persona.alignment}
            name={`${persona.role}-alignment`}
            on:change={(event) => updatePersona(
              index, { ...persona, alignment: event.detail }
            )}
          />
        </div>
      {/each}
    </div>
    <button class="primary-action" onclick={() => navigate('session')}>
      Перейти к дискуссии
    </button>
  {:else}
    <section class="page-heading" aria-labelledby="session-title">
      <p class="index">02 / ГРУППОВОЙ ЧАТ</p>
      <h2 id="session-title">Живая дискуссия</h2>
      <p>Три разных голоса отвечают по очереди и слышат предыдущие реплики.</p>
    </section>

    {#if modelError}
      <aside class="runtime-error" role="alert">
        <strong>Local runtime is not ready</strong>
        <span>{modelError}</span>
        <code>ollama serve</code>
        <button onclick={loadModels}>Retry connection</button>
      </aside>
    {/if}

    {#if models.length}
      <div class="model-strip">
        <strong>Installed Ollama models</strong>
        {#each models as model}
          <span>{model.name} · {model.parameter_size || model.family} ·
            {(model.size / 1024 ** 3).toFixed(2)} GiB</span>
        {/each}
      </div>
    {/if}

    {#if !sessionId}
      <SessionSetup
        value={setup}
        {admission}
        models={models.map(model => model.name)}
        on:change={(event) => updateSetup(event.detail)}
        on:start={(event) => startSession(event.detail)}
      />
      {#if busy}<p class="working">Creating local session…</p>{/if}
    {:else}
      <section class="session-workspace" aria-label="Active dialogue">
        <div class="session-bar">
          <div>
            <span>SESSION {sessionId.slice(0, 8)} · MODE {setup.mode}</span>
            <strong>{streaming ? 'Троица обсуждает сообщение…' : 'Группа ждёт сообщения'}</strong>
          </div>
          <button disabled={streaming} onclick={resetSession}>Новая сессия</button>
        </div>
        <div class="party-strip" aria-label="Участники дискуссии">
          {#each personas as persona}
            <div class:thinking={streaming}>
              <img src={avatarFor(persona.role)} alt="" />
              <span><strong>{persona.name}</strong><small>{classFor(persona.role)}</small></span>
              <i title={streaming ? 'В дискуссии' : 'Готов'}></i>
            </div>
          {/each}
        </div>
        {#if feed.length}
          <DialogueFeed items={feed} {personas} />
        {:else}
          <div class="empty-feed">
            <strong>Все трое в чате</strong>
            <span>Отправьте первое сообщение — каждый ответит своим голосом.</span>
          </div>
        {/if}
        <Composer
          {streaming}
          on:submit={(event) => send(event.detail)}
          on:cancel={cancel}
        />
      </section>
      <MetricsPanel bucket={metrics} />
    {/if}
  {/if}
</main>

<style>
  :global(*) { box-sizing: border-box; }
  :global(body) {
    margin: 0;
    background:
      radial-gradient(circle at 15% -10%, #634a201f, transparent 35%),
      #11100e;
    color: #eee9de;
    font-family: Inter, Arial, sans-serif;
  }
  :global(button) { cursor: pointer; }
  main { min-width: 320px; min-height: 100vh; padding: 36px clamp(20px, 5vw, 72px) 80px; }
  .masthead {
    display: flex;
    align-items: end;
    justify-content: space-between;
    border-bottom: 1px solid #504b42;
  }
  h1 { margin: 6px 0 18px; font: 700 42px Georgia, serif; }
  .eyebrow, .index { color: #c9a86a; font: 12px monospace; letter-spacing: .12em; }
  nav { display: flex; gap: 8px; }
  nav button {
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 14px 18px;
    background: none;
    color: #aaa398;
  }
  nav button.active { border-color: #c9a86a; color: #fff; }
  .notice {
    margin: 14px 0 0;
    border-left: 3px solid #c9a86a;
    padding: 9px 12px;
    color: #d8d1c5;
    background: #191714;
  }
  .page-heading { max-width: 800px; margin: 58px 0 30px; }
  h2 { margin: 10px 0; font: clamp(38px, 6vw, 58px)/1.05 Georgia, serif; }
  .page-heading > p:last-child { color: #aaa398; font-size: 18px; }
  .persona-grid { display: grid; gap: 28px; margin-top: 20px; }
  .persona-editor {
    display: grid;
    grid-template-columns: minmax(340px, .85fr) minmax(440px, 1.15fr);
    gap: 16px;
    align-items: start;
  }
  .primary-action {
    display: block;
    margin: 26px 0 0 auto;
    border: 0;
    padding: 12px 18px;
    background: #c9a86a;
    color: #11100e;
    font-weight: 700;
  }
  .runtime-error, .model-strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    border: 1px solid #c36f58;
    padding: 13px;
    color: #e99b83;
  }
  .runtime-error code { padding: 5px 8px; background: #201b18; color: #eee9de; }
  .runtime-error button { margin-left: auto; }
  .model-strip { border-color: #504b42; color: #aaa398; }
  .model-strip strong { color: #eee9de; }
  .model-strip span { border-left: 1px solid #504b42; padding-left: 10px; font-size: 12px; }
  .session-workspace {
    display: grid;
    gap: 0;
    overflow: hidden;
    margin-bottom: 28px;
    border: 1px solid #504b42;
    border-radius: 8px;
    box-shadow: 0 22px 55px #0007;
  }
  .session-bar { display: flex; justify-content: space-between; padding: 13px 18px; background: #22201c; border-bottom: 1px solid #504b42; }
  .session-bar div { display: grid; gap: 4px; }
  .session-bar span { color: #c9a86a; font: 10px monospace; }
  .session-bar button { background: transparent; color: #aaa398; border: 1px solid #504b42; padding: 7px 10px; }
  .party-strip {
    display: flex;
    gap: 20px;
    overflow-x: auto;
    padding: 11px 18px;
    border-bottom: 1px solid #38342e;
    background: #191714;
  }
  .party-strip > div { display: grid; grid-template-columns: 34px auto 7px; align-items: center; gap: 8px; min-width: 150px; }
  .party-strip img { width: 34px; aspect-ratio: 1; border-radius: 50%; object-fit: cover; border: 1px solid #625b51; }
  .party-strip span { display: grid; gap: 2px; }
  .party-strip strong { font: 12px Georgia, serif; }
  .party-strip small { color: #756f66; font: 9px monospace; text-transform: uppercase; }
  .party-strip i { width: 7px; height: 7px; border-radius: 50%; background: #6f9f77; box-shadow: 0 0 7px #6f9f77; }
  .party-strip .thinking i { background: #c9a86a; box-shadow: 0 0 7px #c9a86a; animation: party-pulse .8s infinite alternate; }
  @keyframes party-pulse { to { opacity: .35; } }
  .empty-feed {
    min-height: 300px;
    display: grid;
    align-content: center;
    justify-items: center;
    gap: 8px;
    background: radial-gradient(circle, #3a302018, transparent 45%), #12110f;
    color: #8e887e;
  }
  .empty-feed strong { color: #d8d1c5; font: 24px Georgia, serif; }
  .empty-feed span { font-size: 13px; }
  .working { color: #c9a86a; }
  @media (max-width: 860px) {
    .persona-editor { grid-template-columns: 1fr; }
    .masthead { align-items: start; gap: 12px; }
    nav button { padding-inline: 8px; }
  }
</style>
