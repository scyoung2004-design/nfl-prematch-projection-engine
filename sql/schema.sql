-- NFL Pre-Match Projection portfolio schema
-- The Python pipeline materializes these tables in outputs/nfl_projection.db.

CREATE TABLE IF NOT EXISTS model_performance (
    market TEXT PRIMARY KEY,
    test_n INTEGER NOT NULL,
    mae REAL NOT NULL,
    rmse REAL NOT NULL,
    bias REAL NOT NULL,
    baseline_mae REAL NOT NULL,
    mae_improvement_pct REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_performance (
    market TEXT NOT NULL,
    week INTEGER NOT NULL,
    n INTEGER NOT NULL,
    mae REAL NOT NULL,
    baseline_mae REAL NOT NULL,
    PRIMARY KEY (market, week)
);

CREATE TABLE IF NOT EXISTS backtest_predictions (
    market TEXT,
    week INTEGER,
    player_id TEXT,
    player_name TEXT,
    position TEXT,
    team TEXT,
    opponent TEXT,
    actual REAL,
    current_volume REAL,
    baseline REAL,
    recent_sd REAL,
    lag1 REAL,
    avg3 REAL,
    avg5 REAL,
    avg8 REAL,
    volume_avg3 REAL,
    volume_avg5 REAL,
    opponent_allowed_avg5 REAL,
    week_index REAL,
    projection REAL,
    error REAL,
    abs_error REAL,
    risk_score REAL,
    risk TEXT,
    confidence TEXT
);
