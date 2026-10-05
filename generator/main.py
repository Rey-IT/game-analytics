import os
import time
import random
import signal
import math
import uuid
from datetime import datetime, timezone, timedelta

import clickhouse_connect
from tenacity import retry, stop_after_attempt, wait_exponential

SEED = int(os.getenv("GENERATOR_SEED", "42"))
BATCH_INTERVAL = float(os.getenv("GENERATOR_BATCH_INTERVAL", "2"))
EVENTS_PER_BATCH = int(os.getenv("GENERATOR_EVENTS_PER_BATCH", "100"))

CH_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CH_USER = os.getenv("CLICKHOUSE_USER", "default")
CH_PASS = os.getenv("CLICKHOUSE_PASSWORD", "")
CH_DB = os.getenv("CLICKHOUSE_DB", "game_analytics")

random.seed(SEED)
running = True


def now_utc_naive():
    """Naive UTC datetime — безопасно для ClickHouse DateTime без таймзоны."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def shutdown(sig, frame):
    global running
    print("Shutdown signal received...")
    running = False


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


@retry(stop=stop_after_attempt(10), wait=wait_exponential(min=1, max=10))
def get_client():
    client = clickhouse_connect.get_client(
        host=CH_HOST, username=CH_USER, password=CH_PASS, database=CH_DB
    )
    client.command("SELECT 1")  # форсируем реальное соединение
    return client


COUNTRIES = ["RU", "US", "DE", "KR", "BR", "JP", "CN"]
EVENT_TYPES = ["kill", "death", "assist", "level_up", "purchase", "boss_kill"]
GAME_MODES = ["ranked", "casual", "arena"]
MAP_NAMES = [
    ("Dust", "desert", "small"),
    ("Mirage", "desert", "medium"),
    ("Forest", "forest", "large"),
    ("Castle", "urban", "medium"),
    ("Ice", "snow", "large"),
]
ITEM_NAMES = {
    "weapon": ["Sword", "Bow", "Staff", "Axe", "Dagger"],
    "armor": ["Helmet", "Chestplate", "Boots", "Shield"],
    "potion": ["Health Potion", "Mana Potion", "Speed Elixir"],
    "skin": ["Golden Skin", "Neon Skin", "Shadow Skin"],
}
RARITIES = ["common", "rare", "epic", "legendary"]


def daily_factor(dt):
    hour = dt.hour + dt.minute / 60
    return 0.3 + 0.7 * max(0, math.sin((hour - 6) / 24 * 2 * math.pi))


def make_players(n=200):
    out = []
    for pid in range(1, n + 1):
        mmr = max(500, min(3500, random.gauss(1500, 400)))
        out.append({
            "player_id": pid,
            "username": f"player_{pid}",
            "country": random.choice(COUNTRIES),
            "rank_tier": min(10, int(mmr / 350) + 1),
            "skill_mmr": float(mmr),
            "created_at": now_utc_naive() - timedelta(days=random.randint(30, 1000)),
        })
    return out


def make_items():
    out, iid = [], 1
    for cat, names in ITEM_NAMES.items():
        for n in names:
            out.append({
                "item_id": iid,
                "item_name": n,
                "category": cat,
                "base_price": float(round(random.uniform(10, 500), 2)),
                "rarity": random.choice(RARITIES),
            })
            iid += 1
    return out


def make_maps():
    return [
        {"map_id": i + 1, "map_name": m, "biome": b, "size_category": s}
        for i, (m, b, s) in enumerate(MAP_NAMES)
    ]


def make_match(players, maps):
    p = random.choice(players)
    win_prob = 0.3 + (p["skill_mmr"] - 500) / 3000 * 0.5
    win_prob = max(0.1, min(0.85, win_prob))
    loss_prob = max(0.0, 1 - win_prob - 0.05)
    result = random.choices(
        ["win", "loss", "draw"],
        weights=[win_prob, loss_prob, 0.05],
    )[0]
    return {
        "match_id": str(uuid.uuid4()),          # строка, а не UUID-объект
        "player_id": int(p["player_id"]),
        "map_id": int(random.choice(maps)["map_id"]),
        "game_mode": random.choice(GAME_MODES),
        "started_at": now_utc_naive(),
        "duration_sec": int(random.randint(300, 3600)),
        "result": result,
        "avg_mmr": float(p["skill_mmr"]),
    }


def make_events_for_match(match, players, items, n):
    player = next(p for p in players if p["player_id"] == match["player_id"])
    mmr = player["skill_mmr"]
    start_time = match["started_at"]
    duration = match["duration_sec"]
    rows = []

    for _ in range(n):
        if mmr > 2000:
            weights = [0.4, 0.1, 0.2, 0.1, 0.1, 0.1]
        else:
            weights = [0.2, 0.3, 0.2, 0.15, 0.1, 0.05]

        etype = random.choices(EVENT_TYPES, weights=weights)[0]
        base = {"kill": 100, "death": -50, "assist": 30,
                "level_up": 20, "purchase": 5, "boss_kill": 300}[etype]
        score = int(base * (1 + mmr / 2000) + random.gauss(0, 15))

        is_anom = 0
        if random.random() < 0.01:
            score = int(score * random.uniform(3, 6))
            is_anom = 1

        item_id = int(random.choice(items)["item_id"]) if etype == "purchase" else 0

        # событие — в случайный момент внутри матча
        offset = random.randint(0, max(1, duration))
        event_time = start_time + timedelta(seconds=offset)

        rows.append([
            str(uuid.uuid4()),                # event_id
            event_time,                       # event_time (naive UTC)
            int(player["player_id"]),         # player_id
            match["match_id"],                # match_id (строка)
            item_id,                          # item_id
            etype,                            # event_type
            match["game_mode"],               # game_mode
            int(random.randint(1, 30)),       # level
            int(score),                       # score
            int(random.randint(500, 30000)),  # duration_ms
            int(is_anom),                     # is_anomaly
        ])
    return rows


def check_no_none(rows, columns):
    """Диагностика: падаем сразу, если в данных есть None."""
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if val is None:
                raise ValueError(
                    f"None in row {i}, column '{columns[j]}': {row}"
                )


def main():
    print("Connecting to ClickHouse...")
    client = get_client()
    print("Seeding reference tables (players, items, maps)...")

    players = make_players(200)
    items = make_items()
    maps = make_maps()

    client.insert(
        "players",
        [[p["player_id"], p["username"], p["country"], p["rank_tier"],
          p["skill_mmr"], p["created_at"]] for p in players],
        column_names=["player_id", "username", "country", "rank_tier",
                      "skill_mmr", "created_at"],
    )

    client.insert(
        "items",
        [[i["item_id"], i["item_name"], i["category"],
          i["base_price"], i["rarity"]] for i in items],
        column_names=["item_id", "item_name", "category", "base_price", "rarity"],
    )

    client.insert(
        "maps",
        [[m["map_id"], m["map_name"], m["biome"], m["size_category"]] for m in maps],
        column_names=["map_id", "map_name", "biome", "size_category"],
    )

    print(f"Seeded: {len(players)} players, {len(items)} items, {len(maps)} maps")
    print("Starting generation loop...")

    matches_cols = ["match_id", "player_id", "map_id", "game_mode",
                    "started_at", "duration_sec", "result", "avg_mmr"]
    events_cols = ["event_id", "event_time", "player_id", "match_id",
                   "item_id", "event_type", "game_mode", "level",
                   "score", "duration_ms", "is_anomaly"]

    try:
        while running:
            now = now_utc_naive()
            n_matches = max(1, int(EVENTS_PER_BATCH * daily_factor(now) / 20))
            matches = [make_match(players, maps) for _ in range(n_matches)]

            match_rows = [
                [m["match_id"], m["player_id"], m["map_id"], m["game_mode"],
                 m["started_at"], m["duration_sec"], m["result"], m["avg_mmr"]]
                for m in matches
            ]
            check_no_none(match_rows, matches_cols)
            client.insert("matches", match_rows, column_names=matches_cols)

            all_events = []
            for m in matches:
                all_events.extend(make_events_for_match(m, players, items, 20))

            check_no_none(all_events, events_cols)
            client.insert("game_events", all_events, column_names=events_cols)

            print(f"Inserted {len(matches)} matches, {len(all_events)} events")
            time.sleep(BATCH_INTERVAL)
    finally:
        print("Shutting down gracefully.")
        client.close()


if __name__ == "__main__":
    main()