import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const metrics = {
  language: 'en',
  mode: 'A',
  ttft: { p50: 120, p95: 120, targetPass: true },
  full: { p50: 800, p95: 800, targetPass: true },
  round: { p50: 2400, p95: 2400, targetPass: true },
  personalityDrift: null,
  personalityDrifted: null,
  worldviewCell: null,
  worldviewDrifted: null,
  integrityReasons: [],
  timeoutRate: 0,
  stateFallbackRate: null,
  errors: []
};

test('session flow with fake local backend through real UI', async ({ page }) => {
  await page.route('**/api/models', route => route.fulfill({ json: [
    {
      name: 'actor-gemma:latest', digest: 'sha256:gemma', size: 900 * 1024 ** 2,
      family: 'gemma', parameter_size: '1B', quantization: 'Q4_K_M'
    },
    {
      name: 'actor-qwen:latest', digest: 'sha256:qwen', size: 1024 ** 3,
      family: 'qwen', parameter_size: '1.5B', quantization: 'Q4_K_M'
    },
    {
      name: 'actor-llama:latest', digest: 'sha256:llama', size: 1300 * 1024 ** 2,
      family: 'llama', parameter_size: '1B', quantization: 'Q4_K_M'
    },
    {
      name: 'state:latest', digest: 'sha256:state', size: 512 * 1024 ** 2,
      family: 'state', parameter_size: '0.6B', quantization: 'Q4_K_M'
    }
  ] }));
  await page.route('**/api/presets', route => route.fulfill({ json: [] }));
  await page.route('**/api/admission', route => route.fulfill({ json: {
    admitted: true,
    reason: 'Local model set fits the selected memory budget',
    actorBytes: 3 * 1024 ** 3,
    stateBytes: 512 * 1024 ** 2,
    reserveBytes: 768 * 1024 ** 2,
    budgetBytes: 8 * 1024 ** 3,
    familiesDistinct: true
  } }));
  await page.route('**/api/sessions', route => route.fulfill({
    status: 201, json: { session_id: 'session-1' }
  }));
  await page.route('**/api/sessions/session-1/metrics', route =>
    route.fulfill({ json: metrics })
  );

  await page.routeWebSocket('**/ws/sessions/session-1', socket => {
    let sequence = 0;
    let turn = 0;
    const send = (kind: string, payload: object) => socket.send(JSON.stringify({
      kind, payload, sequence: ++sequence
    }));
    socket.onMessage(raw => {
      const message = JSON.parse(String(raw));
      if (message.kind === 'user') {
        turn += 1;
        send('state', { phase: 'round_started' });
        if (turn === 1) {
          for (const [index, role, name, text] of [
            [1, 'pragmatist', 'Vector', 'First local reply'],
            [2, 'logician', 'Axiom', 'Second local reply'],
            [3, 'empath', 'Resonance', 'Empath local reply']
          ]) {
            send('utterance', {
              utterance_id: `u${index}`, role, name, state: 'PLANNED'
            });
            send('chunk', { utterance_id: `u${index}`, role, name, text });
            send('utterance', {
              utterance_id: `u${index}`, role, name, state: 'COMPLETED'
            });
          }
          send('state', { phase: 'round_completed' });
        } else {
          send('utterance', {
            utterance_id: 'u4', role: 'pragmatist', name: 'Vector',
            state: 'PLANNED'
          });
          send('chunk', {
            utterance_id: 'u4', role: 'pragmatist', name: 'Vector',
            text: 'Partial local reply'
          });
        }
      }
      if (message.kind === 'cancel') {
        send('utterance', {
          utterance_id: 'u4', role: 'pragmatist', state: 'INTERRUPTED',
          reason: 'user_interrupt'
        });
        send('state', { phase: 'round_completed' });
      }
    });
  });

  await page.goto('/#/session');
  await expect(page.getByRole('heading', { name: 'Живая дискуссия' })).toBeVisible();
  await expect(page.getByText('actor-gemma:latest', { exact: false }).first()).toBeVisible();
  await page.getByLabel('Language').selectOption('en');
  await expect(page.getByText('Admission: PASS')).toBeVisible();
  await page.getByRole('button', { name: 'Start local session' }).click();
  await expect(page.getByText(/Local session session-/)).toBeVisible();

  const composer = page.getByLabel('Сообщение группе');
  await composer.fill('Begin');
  await page.getByRole('button', { name: 'Отправить', exact: true }).click();
  await expect(page.getByText('First local reply')).toBeVisible();
  await expect(page.getByText('Second local reply')).toBeVisible();
  await expect(page.getByText('Empath local reply')).toBeVisible();
  await expect(page.getByText('Группа ждёт сообщения')).toBeVisible();

  await composer.fill('Interrupt this turn');
  await page.getByRole('button', { name: 'Отправить', exact: true }).click();
  await expect(page.getByText('Partial local reply')).toBeVisible();
  await page.getByRole('button', { name: 'Остановить' }).click();
  await expect(page.getByText(/остановлено · user_interrupt/)).toBeVisible();
  await expect(page.getByText('Группа ждёт сообщения')).toBeVisible();
  await expect(page.getByText('120.00 ms').first()).toBeVisible();
});

test('saved preset can be stored and loaded again', async ({ page }) => {
  const defaultPreset = JSON.parse(readFileSync(
    new URL('../../data/presets/default-trio.json', import.meta.url), 'utf8'
  ));
  const stored = [{
    id: 'default-trio', revision: 0, ...defaultPreset
  }];
  await page.route('**/api/models', route => route.fulfill({ json: [] }));
  await page.route('**/api/presets', async route => {
    if (route.request().method() === 'POST') {
      const request = route.request().postDataJSON();
      stored.push({ id: request.id, revision: 1, ...request.preset });
      await route.fulfill({ status: 201, json: stored.at(-1) });
      return;
    }
    await route.fulfill({ json: stored });
  });

  await page.goto('/#/characters');
  await page.getByRole('radio', { name: /Хаотичный добрый/ }).first().check();
  await page.getByLabel('Preset name').fill('custom-trio');
  await page.getByRole('button', { name: 'Save to local server' }).click();
  await expect(page.getByText(/Preset "custom-trio" saved/)).toBeVisible();
  await expect(page.getByLabel('Saved presets')).toContainText('custom-trio · r1');

  await page.getByRole('button', { name: 'Load default' }).click();
  await expect(
    page.getByRole('radio', { name: /Законопослушный нейтральный/ }).first()
  ).toBeChecked();
  await page.getByLabel('Saved presets').selectOption('custom-trio');
  await page.getByRole('button', { name: 'Load saved' }).click();
  await expect(
    page.getByRole('radio', { name: /Хаотичный добрый/ }).first()
  ).toBeChecked();
});

test('session flow real Ollama smoke', async ({ page }) => {
  test.skip(process.env.OLLAMA_SMOKE !== '1', 'set OLLAMA_SMOKE=1');
  await page.goto('/#/session');
  await expect(page.getByRole('heading', { name: 'Живая дискуссия' })).toBeVisible();
});
