# NFL Pre-Match Player Projection & Game Operations Dashboard

A sports analytics portfolio project that turns historical NFL player data into **pre-match player-stat projections, model-monitoring metrics, and an operational review queue**.

The project is designed to demonstrate the kinds of skills used in sports business intelligence and game operations: Python, SQL, predictive modeling, feature engineering, backtesting, dashboarding, data quality thinking, and concise decision support.

> **Independent project:** This project is not affiliated with PrizePicks and does not use or attempt to reproduce any proprietary PrizePicks data, models, trading rules, pricing logic, or internal processes.

## Why this project

PrizePicks describes Player Picks as player-stat projections where the platform sets a projection and users choose whether a player will finish above or below it. That creates a useful public portfolio problem: **how can historical performance, usage, and opponent context be transformed into disciplined pre-game projections and a review workflow?**

This project models three NFL markets:

- QB passing yards
- RB rushing yards
- WR/TE receiving yards

## Holdout results

The model is fitted on **2023 regular-season data** and tested on **2024 regular-season data it did not train on**. Each test-season feature is built using only prior games from that same season, so the backtest avoids using future-game information.

| Market | 2024 test projections | Ridge MAE | Trailing-3 MAE | Improvement |
|---|---:|---:|---:|---:|
| Passing yards | 406 | 64.08 | 68.43 | **6.4%** |
| Rushing yards | 537 | 27.48 | 28.98 | **5.2%** |
| Receiving yards | 1,231 | 26.65 | 29.23 | **8.8%** |

The model beat the recent-form baseline across all three markets on the full 2024 holdout sample. Receiving yards produced the largest relative improvement.

## Modeling approach

The model uses ridge regression because the goal is not just prediction quality; it is also a model that is stable, explainable, and easy to discuss with a business or game-operations partner.

For every eligible player-week, the feature pipeline creates:

- previous-game result (`lag1`)
- trailing 3-game average
- trailing 5-game average
- trailing 8-game average
- trailing 3-game usage average
- trailing 5-game usage average
- opponent's trailing 5-game yards allowed to the relevant position group
- normalized week index

Eligibility thresholds are based only on **prior usage**:

- QB: trailing-3 attempts >= 20
- RB: trailing-3 carries >= 7
- WR/TE: trailing-3 targets >= 4

These filters are a simple approximation of the kinds of players likely to have meaningful pre-match stat markets; they are not intended to replicate any sportsbook or DFS board-selection rules.

## Game-operations risk layer

A projection is not automatically an operationally safe number. The project therefore adds a review score based on:

1. **Model vs. recent-form disagreement** — a large gap between the model projection and trailing-3 average.
2. **Recent volatility** — players whose recent outcomes vary substantially.

Rows are labeled LOW, MEDIUM, or HIGH risk and can be routed to a review queue in SQL or the dashboard.

This is intentionally a **review flag**, not a betting signal. A production system should combine it with information unavailable in this first version, including injuries, depth charts, expected playing time, weather, news, line movement, and manual sport-owner judgment.

## Project structure

```text
nfl-prematch-projection-engine/
├── README.md
├── ATTRIBUTION.md
├── PROJECT_NOTES.md
├── requirements.txt
├── src/
│   └── build_project.py
├── sql/
│   ├── schema.sql
│   └── analysis_queries.sql
├── outputs/
│   ├── model_metrics.csv
│   ├── weekly_metrics.csv
│   ├── model_coefficients.csv
│   └── week18_projection_board.csv
├── dashboard/
│   ├── index.html
│   └── tableau_build_guide.md
└── assets/
    ├── holdout_mae_comparison.png
    ├── weekly_mae_passing_yards.png
    ├── weekly_mae_rushing_yards.png
    └── weekly_mae_receiving_yards.png
```

## Run the full pipeline

From the project folder:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python src/build_project.py
```

The script downloads the 2023 and 2024 weekly files, rebuilds all features, trains the three models, runs the holdout test, writes CSV outputs, creates a SQLite database, generates charts, and rebuilds the HTML dashboard.

Open `dashboard/index.html` in a browser to explore the local dashboard.

## SQL examples

The SQLite output allows questions such as:

- Which market improved most over the trailing-3 baseline?
- Which weeks did the model underperform the heuristic?
- Which player projections should enter a manual review queue?
- Which positions or markets have the highest error?
- Where does the model disagree most with recent form?

See `sql/analysis_queries.sql`.

## Data source

The historical weekly JSON files are hosted in the public `NityaGehlot/nfl-data` repository. Its documented pipeline derives player statistics from `nflreadr` / nflverse and exposes weekly player JSON files with fields including player, position, team, opponent, attempts, carries, targets, passing yards, rushing yards, and receiving yards.

Primary references:

- https://github.com/NityaGehlot/nfl-data
- https://github.com/nflverse/nflverse-data
- https://www.prizepicks.com/help-center/player-picks

## What I would add next

1. Injury and practice-status features.
2. Depth-chart / expected-snap features.
3. Weather and game-environment inputs.
4. Team implied scoring / market context where permitted.
5. Quantile regression to estimate a conditional median rather than only a conditional mean.
6. Walk-forward model refitting instead of a fixed prior-season model.
7. Calibration monitoring by player archetype and projection range.
8. Live ingestion and alerting for late-breaking changes.

## Key takeaway

The most useful result is not that the model predicts every player perfectly—it does not. The useful result is that a transparent, reusable pipeline **improved on a simple recent-form heuristic across all three holdout markets**, while also exposing the cases where a human analyst should investigate further.
