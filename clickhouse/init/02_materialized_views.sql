USE TABLE IF NOT EXISTS events_agg_1m (
    minute DateTime,
    event_type LowCardinality(String),
    game_mode LowCardinality(String),
    events UInt64,
    total_score Int64,
    avg_score Flaot64,
    anomalies Uint64
) ENGINE = SummingMergeTree
ORDER BY (minute, event_type, game_mode);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_events_1m
TO events_agg_1m AS 
SELECT
    toStartOfMinute(event_time) AS minute,
    event_type,
    game_mode,
    count() AS events,
    sum(score) AS total_score,
    avg(score) AS avg_score,
    sum(is_anomaly) AS anomalies
FROM game_events
GROUP BY minute, event_type, game_mode;