<script module lang="ts">
  export interface UserCommand {
    text: string;
    interrupt: boolean;
  }
  export class ComposerController {
    private pending: string | null = null;
    private send: (command: UserCommand) => void;
    private cancel: () => void;
    private defer: (callback: () => void) => void;
    constructor(
      send: (command: UserCommand) => void, cancel: () => void,
      defer: (callback: () => void) => void = queueMicrotask
    ) {
      this.send = send; this.cancel = cancel; this.defer = defer;
    }
    submit(text: string, streaming: boolean): boolean {
      const normalized = text.trim();
      if (!normalized || normalized === this.pending) return false;
      this.pending = normalized;
      this.send({ text: normalized, interrupt: streaming });
      this.defer(() => this.pending = null);
      return true;
    }
    stop() {
      this.cancel();
    }
  }
</script>

<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  let { streaming = false }: { streaming?: boolean } = $props();
  let text = $state('');
  const dispatch = createEventDispatcher<{
    submit: UserCommand;
    cancel: void;
  }>();
  const controller = new ComposerController(
    command => dispatch('submit', command),
    () => dispatch('cancel')
  );
  function submit() {
    if (controller.submit(text, streaming)) text = '';
  }
  function keydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }
</script>

<form onsubmit={(event) => { event.preventDefault(); submit(); }}>
  <label for="composer">Сообщение группе</label>
  <textarea
    id="composer"
    bind:value={text}
    onkeydown={keydown}
    placeholder={streaming
      ? 'Отправить сейчас и перебить текущую реплику…'
      : 'Напишите всем троим…'}
  ></textarea>
  <div>
    {#if streaming}
      <button type="button" class="stop" onclick={() => controller.stop()}>
        Остановить
      </button>
    {/if}
    <button type="submit" disabled={!text.trim()}>
      {streaming ? 'Перебить и отправить' : 'Отправить'}
    </button>
  </div>
</form>

<style>
  form { display: grid; gap: 8px; border-top: 1px solid #504b42; padding: 14px 18px 18px; background: #191714; }
  label { color: #c9a86a; font: 11px monospace; text-transform: uppercase; }
  textarea { min-height: 74px; resize: vertical; border: 1px solid #504b42; border-radius: 7px; background: #11100e; color: #eee9de; padding: 12px; font: inherit; }
  textarea:focus { outline: 2px solid #c9a86a66; border-color: #c9a86a; }
  div { display: flex; justify-content: end; gap: 8px; }
  button { border: 0; background: #c9a86a; padding: 9px 14px; }
  button:disabled { opacity: .4; }
  button.stop { border: 1px solid #c36f58; background: transparent; color: #e99b83; }
</style>
