USE game_analytics;
-- 6. Агрегат событий по минутам
CREATE TABLE IF NOT EXISTS events_agg_1m (
    minute DateTime,
    event_type LowCardinality(String),
    game_mode LowCardinality(String),
    events UInt64,
    total_score Int64,
    avg_score AggregateFunction(avg, Int32),
    anomalies UInt64
) ENGINE = AggregatingMergeTree
ORDER BY (minute, event_type, game_mode);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_events_1m
TO events_agg_1m AS
SELECT
    toStartOfMinute(event_time) AS minute,
    event_type,
    game_mode,
    count() AS events,
    sum(score) AS total_score,
    avgState(score) AS avg_score,
    sum(is_anomaly) AS anomalies
FROM game_events
GROUP BY minute, event_type, game_mode;

-- 7. Читающее представление (для BI, у которого проблемы с AggregateFunction)
CREATE VIEW IF NOT EXISTS events_agg_1m_readable AS
SELECT
    minute,
    event_type,
    game_mode,
    sum(events)          AS events,
    sum(total_score)     AS total_score,
    sum(anomalies)       AS anomalies,
    avgMerge(avg_score)  AS avg_score
FROM events_agg_1m
GROUP BY minute, event_type, game_mode;