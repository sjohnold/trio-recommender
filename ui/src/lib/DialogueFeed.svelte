<script module lang="ts">
  import type { SocketEvent } from './sessionSocket';

  export type FeedState =
    | 'PLANNED' | 'CLAIMED' | 'STREAMING' | 'COMPLETED'
    | 'INTERRUPTED' | 'TIMED_OUT' | 'FAILED';
  export interface FeedItem {
    utteranceId: string;
    role: string;
    name?: string;
    text: string;
    state: FeedState;
    reason?: string;
    lastSequence: number;
  }
  interface Payload {
    utterance_id: string;
    role?: string;
    name?: string;
    text?: string;
    state?: FeedState;
    reason?: string;
  }

  export function applyFeedEvent(
    items: FeedItem[], event: SocketEvent
  ): FeedItem[] {
    if (event.kind !== 'chunk' && event.kind !== 'utterance') return items;
    const payload = event.payload as Payload;
    if (!payload?.utterance_id) throw new Error('utterance_id is required');
    const index = items.findIndex(item => item.utteranceId === payload.utterance_id);
    const current = items[index];
    if (current && event.sequence <= current.lastSequence) return items;
    const next: FeedItem = current ? { ...current } : {
      utteranceId: payload.utterance_id,
      role: payload.role ?? 'unknown',
      name: payload.name,
      text: '',
      state: 'PLANNED',
      lastSequence: 0
    };
    next.lastSequence = event.sequence;
    if (payload.role) next.role = payload.role;
    if (payload.name) next.name = payload.name;
    if (event.kind === 'chunk') {
      next.text += payload.text ?? '';
      next.state = 'STREAMING';
    } else {
      next.state = payload.state ?? next.state;
      next.reason = payload.reason;
      if (!current && payload.text) next.text = payload.text;
    }
    if (index < 0) return [...items, next];
    return items.map((item, position) => position === index ? next : item);
  }
</script>

<script lang="ts">
  import type { PersonaConfig, Role } from './api';

  let {
    items,
    personas = []
  }: { items: FeedItem[]; personas?: PersonaConfig[] } = $props();
  const roleVisuals: Record<string, {
    title: string;
    avatar: string;
    accent: string;
  }> = {
    pragmatist: { title: 'Прагматик', avatar: '/avatars/vector.png', accent: '#d47a3a' },
    logician: { title: 'Логик', avatar: '/avatars/axiom.png', accent: '#4da6a8' },
    empath: { title: 'Эмпат', avatar: '/avatars/resonance.png', accent: '#a875c2' },
    user: { title: 'Вы', avatar: '', accent: '#8e887e' },
    unknown: { title: 'Неизвестно', avatar: '', accent: '#8e887e' }
  };
  const broken = (state: FeedState) =>
    ['INTERRUPTED', 'TIMED_OUT', 'FAILED'].includes(state);
  const visual = (role: string) => roleVisuals[role] ?? roleVisuals.unknown;
  const displayName = (item: FeedItem) =>
    item.name
    ?? personas.find(persona => persona.role === item.role as Role)?.name
    ?? visual(item.role).title;
  const stateLabel = (state: FeedState) => ({
    PLANNED: 'ждёт реплики',
    CLAIMED: 'готовится',
    STREAMING: 'печатает…',
    COMPLETED: '',
    INTERRUPTED: 'остановлено',
    TIMED_OUT: 'не успел ответить',
    FAILED: 'ошибка ответа'
  }[state]);
</script>

<ol aria-label="Групповая дискуссия" aria-live="polite">
  {#each items as item (item.utteranceId)}
    {@const details = visual(item.role)}
    <li
      class:user={item.role === 'user'}
      class:streaming={item.state === 'STREAMING'}
      style={`--speaker: ${details.accent}`}
    >
      <div class="avatar" aria-hidden="true">
        {#if details.avatar}
          <img src={details.avatar} alt="" />
        {:else}
          <span>{displayName(item).slice(0, 1)}</span>
        {/if}
      </div>
      <div class="message">
        <header>
          <strong>{displayName(item)}</strong>
          {#if item.role !== 'user'}<span>{details.title}</span>{/if}
          {#if stateLabel(item.state)}
            <em>{stateLabel(item.state)}</em>
          {/if}
        </header>
        {#if item.text}
          <p>{item.text}<span class="cursor" aria-hidden="true">
            {item.state === 'STREAMING' ? '▋' : ''}
          </span></p>
        {:else if item.state === 'PLANNED'}
          <div class="typing" aria-label="Ожидает очереди"><i></i><i></i><i></i></div>
        {/if}
        {#if broken(item.state)}
          <small class="broken">{stateLabel(item.state)} · {item.reason ?? item.state}</small>
        {/if}
      </div>
    </li>
  {/each}
</ol>

<style>
  ol {
    display: grid;
    gap: 18px;
    min-height: 300px;
    max-height: min(62vh, 760px);
    overflow-y: auto;
    margin: 0;
    padding: 24px;
    list-style: none;
    background:
      radial-gradient(circle at 20% 0%, #6d583014, transparent 38%),
      #12110f;
    scrollbar-color: #504b42 #12110f;
  }
  li {
    display: grid;
    grid-template-columns: 46px minmax(0, 1fr);
    align-items: end;
    gap: 10px;
    max-width: min(78%, 780px);
  }
  li.user {
    grid-template-columns: minmax(0, 1fr) 38px;
    justify-self: end;
  }
  li.user .avatar { grid-column: 2; grid-row: 1; width: 38px; }
  li.user .message { grid-column: 1; grid-row: 1; border-color: #5c5141; background: #2a251d; }
  li.user header { justify-content: flex-end; }
  .avatar {
    overflow: hidden;
    width: 46px;
    aspect-ratio: 1;
    border: 2px solid var(--speaker);
    border-radius: 50%;
    background: #24211d;
    box-shadow: 0 3px 12px #0008;
  }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .avatar span { display: grid; height: 100%; place-items: center; color: #ddd2c2; font: 19px Georgia, serif; }
  .message {
    position: relative;
    min-width: 150px;
    border: 1px solid color-mix(in srgb, var(--speaker) 40%, #38342e);
    border-left: 3px solid var(--speaker);
    border-radius: 5px 13px 13px 13px;
    padding: 11px 14px 12px;
    background: color-mix(in srgb, var(--speaker) 7%, #1b1916);
    box-shadow: 0 6px 16px #0003;
  }
  li.streaming .message { box-shadow: 0 0 22px color-mix(in srgb, var(--speaker) 15%, transparent); }
  header { display: flex; align-items: baseline; gap: 8px; }
  header strong { color: var(--speaker); font: 700 13px Georgia, serif; }
  header span {
    color: #756f66;
    font: 9px monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
  }
  header em { margin-left: auto; color: #8f887e; font: 9px monospace; font-style: normal; }
  p { margin: 7px 0 0; white-space: pre-wrap; line-height: 1.55; }
  .cursor { color: var(--speaker); }
  .broken { display: block; margin-top: 8px; color: #e99b83; }
  .typing { display: flex; gap: 4px; padding: 9px 2px 2px; }
  .typing i {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--speaker);
    animation: pulse 1s infinite alternate;
  }
  .typing i:nth-child(2) { animation-delay: .2s; }
  .typing i:nth-child(3) { animation-delay: .4s; }
  @keyframes pulse { to { opacity: .25; transform: translateY(-2px); } }
  @media (max-width: 680px) {
    ol { padding: 14px 10px; }
    li { max-width: 94%; grid-template-columns: 36px minmax(0, 1fr); }
    .avatar { width: 36px; }
  }
</style>
