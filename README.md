# Game Analytics — End-to-end система сбора и анализа игровой статистики

Учебный проект: production-подобная система, которая генерирует поток
игровых событий, сохраняет их в ClickHouse, агрегирует в реальном времени
и позволяет анализировать через Apache Superset и Jupyter Notebook.

---

## Предметная область

**Игровая статистика.** Система моделирует поведение игроков в
многопользовательской игре: матчи, игровые события (убийства, покупки,
повышения уровня) и справочники игроков, предметов и карт.

Ключевой скрытый параметр — **`skill_mmr`** (рейтинг навыка игрока).
Он влияет на:
- вероятность победы в матче;
- тип генерируемых событий (сильные игроки чаще делают `kill` и `boss_kill`);
- величину `score` за событие;
- частоту «аномалий» (бустерских матчей).

---

## Архитектура

```
┌──────────────────┐
│  Генератор       │  Python-сервис, пишет батчами раз в 2 сек
│  (Python)        │
└────────┬─────────┘
         │  INSERT (batch)
         ▼
┌──────────────────┐
│  ClickHouse      │  5 таблиц + Materialized View (агрегат по минутам)
│  (аналитич. СУБД)│
└────────┬─────────┘
         │
   ┌─────┴─────┐
   ▼           ▼
┌─────────┐ ┌─────────┐
│Superset │ │ Jupyter │
│(дашборд)│ │(анализ) │
└─────────┘ └─────────┘
```

---

## Схема данных (5 таблиц + MV)

| Таблица | Роль | Связи |
|---|---|---|
| `players` | справочник игроков | PK `player_id` |
| `items` | справочник предметов | PK `item_id` |
| `maps` | справочник карт | PK `map_id` |
| `matches` | матчи игроков | FK → `players`, `maps` |
| `game_events` | игровые события | FK → `players`, `matches`, `items` |

Материализованные представления:

- `events_agg_1m` — таблица-приёмник агрегата (`AggregatingMergeTree`).
- `mv_events_1m` — материализованное представление, пишет в `events_agg_1m`
  через `avgState`/`sum` при вставке событий.
- `events_agg_1m_readable` — читающее представление (`View`) для BI: оборачивает
  `avg_score` в `avgMerge`, чтобы Superset видел обычный `Float64`.

> ⚠️ Напрямую из `events_agg_1m` читать `avg_score` нельзя — там лежит
> бинарное состояние агрегата. Используйте `events_agg_1m_readable` или
> оборачивайте в `avgMerge(...) GROUP BY`.

---

## Стек

- **Генератор:** Python 3.11, clickhouse-connect, tenacity
- **БД:** ClickHouse 24.3 (MergeTree, ReplacingMergeTree, AggregatingMergeTree, Materialized View)
- **BI:** Apache Superset (появится позже) + PostgreSQL (метаданные) + Redis (кэш)
- **Анализ:** Jupyter Notebook + pandas + matplotlib (появится позже)
- **Инфраструктура:** Docker Compose

---

## Что уже работает

- ✅ ClickHouse поднимается, `healthy`, слушает `8123` (HTTP) и `9000` (native).
- ✅ Init-скрипты создают 5 таблиц, 1 MV и 1 читающее представление.
- ✅ Генератор засеивает справочники: **200 игроков, 15 предметов, 5 карт**.
- ✅ В цикле пишет **4 матча / 80 событий** каждые 2 секунды (значения зависят
  от `daily_factor` — «суточного профиля»).
- ✅ За час работы накапливается ~40 тыс. событий, `events_agg_1m` — ~1.3 тыс.
  строк агрегата.
- ✅ Все проверки целостности проходят: события разнесены по времени матча,
  аномалии (`is_anomaly = 1`) выделяются в 3–6 раз по `score`.

---

## Запуск

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Rey-IT/game-analytics.git
cd game-analytics

# 2. Скопировать переменные окружения
cp .env.example .env
# отредактировать .env при необходимости (пароли, seed)

# 3. Поднять всю систему в фоне
docker compose up -d --build

# 4. Проверить, что контейнеры поднялись
docker compose ps

# 5. Смотреть логи генератора
docker compose logs -f generator
```

После старта:
- ClickHouse HTTP: http://localhost:8123 (ping: `curl http://localhost:8123/ping`)
- Superset: http://localhost:8088 (появится позже)
- Jupyter: http://localhost:8888 (появится позже)

---

## Порты сервисов

| Сервис | Порт | Логин / пароль |
|---|---|---|
| ClickHouse (HTTP) | 8123 | `default` / `clickhouse123` |
| ClickHouse (native) | 9000 | `default` / `clickhouse123` |
| Superset | 8088 | `admin` / `admin` (появится позже) |
| Jupyter | 8888 | без пароля, токен отключён (появится позже) |

---

## Переменные окружения

Все креды и настройки — в `.env` (в репозиторий кладётся только `.env.example`).

| Переменная | Назначение |
|---|---|
| `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` | доступ к ClickHouse |
| `CLICKHOUSE_DB` | имя БД (`game_analytics`) |
| `POSTGRES_*` | метабаза Superset (появится позже) |
| `SUPERSET_*` | админ Superset и secret key (появится позже) |
| `GENERATOR_SEED` | seed генератора (воспроизводимость) |
| `GENERATOR_BATCH_INTERVAL` | интервал между батчами (сек) |
| `GENERATOR_EVENTS_PER_BATCH` | базовое число событий в батче |

---

## Полезные команды

```bash
# Логи
docker compose logs -f generator
docker compose logs -f clickhouse

# Статус
docker compose ps

# Зайти в clickhouse-client
docker exec -it clickhouse clickhouse-client --password clickhouse123

# Остановить, сохранив данные
docker compose stop
docker compose start

# Удалить контейнеры, сохранив данные (volume)
docker compose down

# Полный сброс (удалить данные и пересоздать таблицы из init-скриптов)
docker compose down -v
docker compose up -d --build
```

> ⚠️ Init-скрипты ClickHouse выполняются **только при пустом volume**.
> Если вы правите `clickhouse/init/*.sql` — обязательно `docker compose down -v`
> перед следующим `up`.

---

## Структура репозитория

```
game-analytics/
├── docker-compose.yml
├── .env.example
├── README.md
├── clickhouse/
│   └── init/
│       ├── 01_tables.sql
│       └── 02_materialized_views.sql
├── generator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── superset/
│   └── (появится позже)
├── jupyter/
│   └── (появится позже)
└── docs/
    └── (скриншоты появятся позже)
```

---

## Разработка (локально, без Docker)

Для правки `generator/main.py` удобно держать venv:

```powershell
cd game-analytics
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r generator/requirements.txt
python -m pip install exceptiongroup   # для isort в VS Code на Python 3.10
```

В VS Code: `Ctrl+Shift+P` → **Python: Select Interpreter** → `./.venv/Scripts/python.exe`.

---

## Скриншоты

_(Будут добавлены после настройки Superset и Jupyter.)_

- Дашборд Superset — `docs/superset_dashboard.png`
- Графики из Jupyter — `docs/jupyter_plots.png`