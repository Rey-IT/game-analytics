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

## Схема данных (5 таблиц)

| Таблица | Роль | Связи |
|---|---|---|
| `players` | справочник игроков | PK `player_id` |
| `items` | справочник предметов | PK `item_id` |
| `maps` | справочник карт | PK `map_id` |
| `matches` | матчи игроков | FK → `players`, `maps` |
| `game_events` | игровые события | FK → `players`, `matches`, `items` |

Плюс Materialized View `mv_events_1m` — агрегат событий по минутам и категориям
в реальном времени.

---

## Стек

- **Генератор:** Python 3.11, clickhouse-connect, tenacity
- **БД:** ClickHouse 24.3 (MergeTree, SummingMergeTree, Materialized View)
- **BI:** Apache Superset 3.1 + PostgreSQL (метаданные) + Redis (кэш)
- **Анализ:** Jupyter Notebook + pandas + matplotlib
- **Инфраструктура:** Docker Compose

---

## Запуск

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Rey-IT/game-analytics.git
cd game-analytics

# 2. Скопировать переменные окружения
cp .env.example .env

# 3. Поднять всю систему
docker compose up
```

После старта:
- ClickHouse HTTP: http://localhost:8123
- Superset: http://localhost:8088
- Jupyter: http://localhost:8888

---

## Порты сервисов

| Сервис | Порт | Логин / пароль |
|---|---|---|
| ClickHouse (HTTP) | 8123 | `default` / `clickhouse123` |
| ClickHouse (native) | 9000 | `default` / `clickhouse123` |
| Superset | 8088 | `admin` / `admin` |
| Jupyter | 8888 | без пароля (токен отключён) |

---

## Переменные окружения

Все креды и настройки — в `.env` (в репозиторий кладётся только `.env.example`).

| Переменная | Назначение |
|---|---|
| `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` | доступ к ClickHouse |
| `CLICKHOUSE_DB` | имя БД (`game_analytics`) |
| `POSTGRES_*` | метабаза Superset |
| `SUPERSET_*` | админ Superset и secret key |
| `GENERATOR_SEED` | seed генератора (воспроизводимость) |
| `GENERATOR_BATCH_INTERVAL` | интервал между батчами (сек) |
| `GENERATOR_EVENTS_PER_BATCH` | базовое число событий в батче |

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

## Скриншоты

_(Будут добавлены после настройки Superset и Jupyter.)_

- Дашборд Superset — `docs/superset_dashboard.png`
- Графики из Jupyter — `docs/jupyter_plots.png`