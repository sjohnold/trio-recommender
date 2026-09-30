# Trio

Локальное веб-приложение для диалогов трёх настраиваемых ИИ-персон и исследования
content-based рекомендаций реплик. Проект объединяет FastAPI, WebSocket, SQLite,
Svelte и Ollama; все данные и inference остаются на компьютере пользователя.

## Рекомендательная система

Trio содержит content-based recommender для подбора few-shot voice examples к
текущей конфигурации персонажа. Пайплайн разделён на понятные стадии:

1. candidate generation — жёсткие фильтры языка, письменности и роли;
2. scoring — версионированная взвешенная дистанция по семи признакам личности
   плюс штраф за несовпадение alignment;
3. re-ranking — стабильный top-k, дедупликация текста и topic diversity;
4. serving — API возвращает полный ranking, компоненты решения и флаг `selected`;
5. evaluation — unit-тесты проверяют фильтры, устойчивость ranking, diversity,
   дедупликацию и shortage behavior.

Посмотреть реальное решение ранжировщика можно через
`POST /api/recommendations/voice-examples`. Пример тела запроса:

```json
{
  "language": {"language": "en"},
  "role": "logician",
  "stats": {
    "energy": 5, "openness": 5, "nerve": 5, "sharpness": 5,
    "reasoning": 8, "provocation": 5, "attunement": 5
  },
  "alignment": "true_neutral",
  "limit": 3
}
```

Это локальный, детерминированный baseline. Следующий production-шаг — логировать
показы/выборы, считать Precision@K и coverage по сегментам, а затем сравнить
ручные веса с learning-to-rank на накопленной обратной связи.

## Первый запуск

Нужны Python 3.11+, Node.js 20+ и запущенный Ollama.

```bash
cd /path/to/Trio
python3 -m pip install -e ".[test]"
npm --prefix ui install
```

Для Mode A нужны три actor-модели разных семейств и отдельная State Model.
Проверенный на этой машине набор:

```bash
/home/sjohnold/mnt/new-tom/ollama/bin/ollama pull gemma3:1b
/home/sjohnold/mnt/new-tom/ollama/bin/ollama pull qwen2.5:1.5b
/home/sjohnold/mnt/new-tom/ollama/bin/ollama pull llama3.2:1b
/home/sjohnold/mnt/new-tom/ollama/bin/ollama pull qwen2.5:0.5b
```

Ollama должна разрешать четыре одновременно загруженные модели. Для
пользовательского systemd-сервиса:

```bash
install -D -m 644 config/ollama-mode-a.conf \
  "$HOME/.config/systemd/user/ollama.service.d/trio-mode-a.conf"
systemctl --user daemon-reload
systemctl --user restart ollama
```

Если Ollama запускается вручную, используйте:

```bash
OLLAMA_MAX_LOADED_MODELS=4 OLLAMA_NUM_PARALLEL=1 \
  /home/sjohnold/mnt/new-tom/ollama/bin/ollama serve
```

В другом терминале запустите Trio одной командой:

```bash
cd /path/to/Trio
./scripts/dev.sh
```

Откройте <http://127.0.0.1:5173/#/session>. UI сам загрузит локальный список
моделей и выберет Mode A: три наименьшие actor-модели разных семейств и
отдельную наименьшую State Model. Нажмите **Start local session**, затем
отправьте сообщение. Первый старт предзагружает все четыре модели и поэтому
может занять дольше последующих.

SQLite создаётся автоматически в `data/trio.db`. Порты по умолчанию:
backend `127.0.0.1:8000`, UI `127.0.0.1:5173`, Ollama
`127.0.0.1:11434`.

## Пресеты

На вкладке **Characters** измените параметры, введите имя в **Preset name** и
нажмите **Save to local server**. Сохранённая версия появится в
**Saved presets**; выберите её и нажмите **Load saved**. Повторное сохранение
под тем же именем создаёт новую ревизию в локальной SQLite. Import/Export JSON
остаются отдельными файловыми операциями.

## Проверка

```bash
pytest
npm --prefix ui test -- --run
npm --prefix ui run build
npm --prefix ui run test:e2e
```

С запущенными backend и Ollama настоящий раунд Mode A со всеми тремя ролями,
четырьмя резидентными моделями и нулевым State fallback проверяет:

```bash
python3 scripts/smoke_local.py --mode A
```

Для отдельной проверки Mode B используйте `--mode B`.
