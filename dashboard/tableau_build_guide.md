# Tableau / Power BI Build Guide

Use these outputs:

- `outputs/week18_projection_board.csv` for the projection board.
- `outputs/weekly_metrics.csv` for weekly model-monitoring visuals.
- `outputs/model_metrics.csv` for KPI cards.

## Page 1 — Projection Board

Filters: Market, Position, Team, Opponent, Risk, Confidence.

Columns to show: Player, Market, Team, Opponent, Projection, Recent Avg 3, Confidence, Risk.

Suggested conditional formatting:

- HIGH risk: strongest warning emphasis.
- MEDIUM risk: secondary warning emphasis.
- LOW risk: neutral / normal operating state.

## Page 2 — Model Performance

KPI cards: MAE, Baseline MAE, Improvement %, Test N.

Charts:

1. Weekly MAE vs. baseline MAE by market.
2. Projection vs. actual scatterplot.
3. Error distribution by market.
4. MAE by position.

## Page 3 — Game Operations Review Queue

Filter to `risk IN ('HIGH','MEDIUM')` and sort descending by `risk_score`.

Add fields for projection, recent average, opponent, and model-vs-baseline disagreement. In a production environment, this view should also include injuries, depth-chart changes, expected playing time, late news, and market movement.
