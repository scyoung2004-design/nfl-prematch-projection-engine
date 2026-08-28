-- 1) Portfolio scorecard: where does the model beat recent-form heuristics?
SELECT
    market,
    test_n,
    mae,
    baseline_mae,
    ROUND(baseline_mae - mae, 2) AS mae_reduction,
    mae_improvement_pct
FROM model_performance
ORDER BY mae_improvement_pct DESC;

-- 2) Weeks where model performance deteriorated relative to the baseline.
SELECT
    market,
    week,
    n,
    mae,
    baseline_mae,
    ROUND(mae - baseline_mae, 2) AS model_minus_baseline
FROM weekly_performance
WHERE mae > baseline_mae
ORDER BY model_minus_baseline DESC;

-- 3) Operational review queue: highest-risk projection rows.
SELECT
    week,
    market,
    player_name,
    team,
    opponent,
    ROUND(projection, 1) AS projection,
    ROUND(baseline, 1) AS recent_avg3,
    confidence,
    risk,
    ROUND(risk_score, 2) AS risk_score
FROM backtest_predictions
WHERE risk IN ('HIGH', 'MEDIUM')
ORDER BY
    CASE risk WHEN 'HIGH' THEN 1 ELSE 2 END,
    risk_score DESC;

-- 4) Projection error by position.
SELECT
    market,
    position,
    COUNT(*) AS projections,
    ROUND(AVG(abs_error), 2) AS mae
FROM backtest_predictions
GROUP BY market, position
ORDER BY market, mae;

-- 5) Players whose model projection diverged most from recent form.
SELECT
    week,
    market,
    player_name,
    team,
    opponent,
    ROUND(projection, 1) AS projection,
    ROUND(baseline, 1) AS recent_avg3,
    ROUND(ABS(projection - baseline), 1) AS disagreement
FROM backtest_predictions
ORDER BY disagreement DESC
LIMIT 25;
