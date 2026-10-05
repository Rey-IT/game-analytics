CREATE DATABASE IF NOT EXISTS game_analytics;
USE game_analytics;

-- 1. Игроки
CREATE TABLE IF NOT EXISTS players (
    player_id UInt32,
    username String,
    country LowCardinality(String),
    rank_tier UInt8,
    skill_mmr Float32,
    created_at DateTime
) ENGINE = ReplacingMergeTree
ORDER BY player_id;

-- 2. Предметы
CREATE TABLE IF NOT EXISTS items (
    item_id UInt16,
    item_name String,
    category LowCardinality(String),
    base_price Float32,
    rarity LowCardinality(String)
) ENGINE = ReplacingMergeTree
ORDER BY item_id;

-- 3. Карты
CREATE TABLE IF NOT EXISTS maps (
    map_id UInt8,
    map_name String,
    biome LowCardinality(String),
    size_category LowCardinality(String)
) ENGINE = ReplacingMergeTree
ORDER BY map_id;

-- 4. Матчи
CREATE TABLE IF NOT EXISTS matches (
    match_id UUID,
    player_id UInt32,
    map_id UInt8,
    game_mode LowCardinality(String),
    started_at DateTime,
    duration_sec UInt32,
    result LowCardinality(String),
    avg_mmr Float32
) ENGINE = MergeTree
PARTITION BY toDate(started_at)
ORDER BY (started_at, player_id);

-- 5. События
CREATE TABLE IF NOT EXISTS game_events (
    event_id UUID,
    event_time DateTime,
    player_id UInt32,
    match_id UUID,
    item_id UInt16,
    event_type LowCardinality(String),
    game_mode LowCardinality(String),
    level UInt8,
    score Int32,
    duration_ms UInt32,
    is_anomaly UInt8
) ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (event_time, player_id, event_type);