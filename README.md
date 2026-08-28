# NFL 2026 Pre-Match Player Projection & Game Operations Dashboard

A sports analytics portfolio project that turns historical NFL player data into **forward-looking player-stat projections, model-validation metrics, and an operational review queue**.

The project is designed to demonstrate skills used in sports business intelligence and game operations: Python, SQL, predictive modeling, feature engineering, backtesting, dashboarding, data quality thinking, and concise decision support.

### [View the 2026 Week 1 interactive dashboard](https://scyoung2004-design.github.io/nfl-prematch-projection-engine/)

> **Independent project:** This project is not affiliated with PrizePicks and does not use or attempt to reproduce any proprietary PrizePicks data, models, trading rules, pricing logic, or internal processes.

## Why this project

Player-projection products create a useful public analytics problem: **how can historical performance, recent workload, and opponent context be transformed into disciplined pre-game projections and a review workflow?**

This project models three NFL markets:

- QB passing yards
- RB rushing yards
- WR/TE receiving yards

The project began as a historical backtest and was then extended into a **2026 forward-looking Week 1 projection board**.

### Historical backtest

The first version of the project focused on proving the modeling approach before generating forward-looking projections. It trained on **2023 regular-season data** and evaluated on **unseen 2024 player-games**, comparing ridge-regression projections against a trailing-3-game baseline across passing, rushing, and receiving yards.

### [View the original historical backtest dashboard](https://scyoung2004-design.github.io/nfl-prematch-projection-engine/backtesting.html)

That historical stage established the project’s core workflow: build time-aware features, prevent data leakage, benchmark against a simple heuristic, measure out-of-sample error, and flag projections that deserve manual review. The later 2025 validation and 2026 Week 1 board extend that same framework rather than replacing it.

## Modeling and validation workflow

The current version follows a time-aware modeling process:

1. Use **2023-2024 historical NFL data** to develop and fit the validation models.
2. Test those models on **unseen 2025 player-games**.
3. Compare model MAE against a trailing-3-game recent-form baseline.
4. Refit the final projection framework using **2023-2025 history**.
5. Generate **2026 Week 1 pre-match projections** for eligible returning players.

Features are calculated from information available before the projected game rather than from future outcomes.

## 2025 holdout results

The 2025 season serves as an out-of-sample validation set before generating the 2026 board.

| Market | 2025 test projections | Model MAE | Trailing-3 MAE | Improvement |
|---|---:|---:|---:|---:|
| Passing yards | 402 | 62.11 | 69.79 | **11.0%** |
| Rushing yards | 577 | 27.08 | 29.66 | **8.7%** |
| Receiving yards | 1,210 | 26.08 | 28.18 | **7.4%** |

Across all three markets, the validation sample contains **2,189 player-game projections**. The model improved on the trailing-3 baseline in every market.

> MAE is measured in yards, so MAE values should be interpreted within each market rather than compared directly across passing, rushing, and receiving.

## 2026 Week 1 projection board

The published dashboard contains a featured set of 2026 Week 1 projections and allows filtering by:

- market
- risk level
- player or team search

Each row includes:

- model projection
- trailing-3 average
- trailing-5 average
- recent workload
- opponent trailing-5 yards allowed
- historical games available
- manual-review risk level

The dashboard is a **forward-looking portfolio demonstration**, not a wagering recommendation.

The published featured board is also preserved in `outputs/2026_week1_featured_board.csv`, and the validation metrics shown on the dashboard are preserved in `outputs/2025_validation_metrics.csv`.

## Game-operations risk layer

A projection is not automatically operationally safe. The project adds a review layer intended to identify cases that deserve additional analyst attention.

Risk is driven by factors such as:

1. **Model vs. recent-form disagreement**
2. **Recent player volatility**

Rows are labeled **LOW, MEDIUM, or HIGH** risk.

A HIGH-risk row does **not** mean a player is expected to go over or under the projection. It means a Game Operations analyst should investigate additional context such as injuries, role changes, depth chart, expected snaps, weather, and late news before relying on the estimate.

## Modeling approach

Ridge regression was selected as the first modeling framework because rolling-performance and workload features are naturally correlated. Regularization helps stabilize the coefficients while keeping the model interpretable.

The feature set centers on prior-game information such as:

- previous-game production
- trailing 3-game performance
- trailing 5-game performance
- longer recent-history averages where available
- recent attempts, carries, or targets
- opponent recent yards allowed to the relevant position group

Eligibility is based on prior workload so that the board focuses on players with enough recent usage and historical information to support a meaningful estimate.

## Project structure

```text
nfl-prematch-projection-engine/
├── README.md
├── ATTRIBUTION.md
├── PROJECT_NOTES.md
├── REPRODUCIBILITY.md
├── .gitignore
├── requirements.txt
├── src/
│   ├── build_project.py
│   └── build_live_2026.py
├── sql/
│   ├── schema.sql
│   └── analysis_queries.sql
├── outputs/
│   ├── model_metrics.csv
│   ├── weekly_metrics.csv
│   ├── model_coefficients.csv
│   ├── week18_projection_board.csv
│   ├── 2025_validation_metrics.csv
│   └── 2026_week1_featured_board.csv
├── dashboard/
│   ├── index.html
│   └── tableau_build_guide.md
├── docs/
│   ├── index.html
│   └── backtesting.html
└── assets/
    ├── holdout_mae_comparison.png
    ├── weekly_mae_passing_yards.png
    ├── weekly_mae_rushing_yards.png
    └── weekly_mae_receiving_yards.png
```

The files in `outputs/` and `assets/` preserve the original historical backtest artifacts as well as fixed snapshots of the published 2025 validation and 2026 featured board. The GitHub Pages site in `docs/index.html` is the forward-looking 2026 Week 1 portfolio dashboard.

## Reproduce the 2026 board

The repository now includes a reproducible forward-looking pipeline rather than only the published HTML dashboard.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/build_live_2026.py
```

The live script rebuilds the 2025 validation, refits the model on 2023-2025 history, downloads the 2026 nflverse roster and schedule, generates the Week 1 board, writes review/omission outputs, and rebuilds both the local and GitHub Pages dashboards.

The exact values currently published on the portfolio dashboard are also preserved as fixed CSV snapshots in `outputs/2025_validation_metrics.csv` and `outputs/2026_week1_featured_board.csv`. Because the 2026 roster is a live upstream source, a later rerun can change as roster information changes.

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the full rebuild notes.

## Run the historical pipeline

From the project folder:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/build_project.py
```

The historical pipeline downloads weekly NFL files, rebuilds features, trains the models, runs the holdout test, writes CSV outputs, generates a local SQLite database, creates charts, and rebuilds the historical HTML dashboard.

The generated SQLite database is not tracked in this repository.

## SQL examples

The SQL layer supports analyst-style questions such as:

- Which market improved most over the recent-form baseline?
- Which weeks did the model underperform?
- Which projections should enter a manual review queue?
- Which positions or markets have the highest error?
- Where does the model disagree most with recent form?

See `sql/analysis_queries.sql`.

## Data source

Historical weekly NFL files come from the public `NityaGehlot/nfl-data` repository, whose documented pipeline derives player statistics from `nflreadr` / nflverse.

Primary references:

- https://github.com/NityaGehlot/nfl-data
- https://github.com/nflverse/nflverse-data
- https://www.prizepicks.com/help-center/player-picks

See `ATTRIBUTION.md` for additional project attribution.

## Current limitations

The 2026 board is a portfolio model built from historical football data. It does not currently incorporate every piece of information a production Game Operations team would use.

Important missing or simplified inputs include:

- real-time injuries and practice status
- confirmed depth charts and starting roles
- expected snap counts
- weather
- late-breaking news
- market movement
- manual sport-owner adjustments

The risk layer is designed partly to surface cases where those missing inputs matter most.

## What I would add next

1. Injury and practice-status features.
2. Depth-chart and expected-snap features.
3. Weather and game-environment inputs.
4. Automated weekly 2026 refreshes.
5. Quantile regression for conditional-median projections.
6. Walk-forward model refitting.
7. Calibration monitoring by player archetype and projection range.
8. Alerts for major late-breaking projection changes.

## Key takeaway

The project demonstrates a complete analytics workflow: **develop a model, validate it on unseen data, compare it against a simple benchmark, identify operational risk, and then use the validated framework to create forward-looking projections.**

The objective is not to claim perfect player forecasting. It is to build a transparent, reusable decision-support process that improves on a simple recent-form heuristic while clearly identifying cases that deserve human review.
