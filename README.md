# NFL 2026 Pre-Match Player Projection Engine

A sports analytics portfolio project that uses historical NFL data to **validate predictive models, generate forward-looking player-stat projections, and flag high-uncertainty cases for manual review**.

**Tech:** Python · SQL · Ridge Regression · Feature Engineering · Backtesting · Dashboarding

### [View the 2026 Week 1 interactive dashboard](https://scyoung2004-design.github.io/nfl-prematch-projection-engine/)

> **Independent project:** This project is not affiliated with PrizePicks and does not use or attempt to reproduce proprietary PrizePicks data, pricing logic, trading rules, or internal models.

## Project overview

The project asks a practical Game Operations question:

> **How can recent player performance, workload, and opponent context be turned into disciplined pre-match projections and a repeatable review workflow?**

It models three NFL player-stat markets:

- QB passing yards
- RB rushing yards
- WR/TE receiving yards

The project began as a historical backtest, then progressed to an unseen-season validation and a forward-looking **2026 Week 1 projection board**.

## Validation results

Models were developed on **2023–2024 history** and tested on **unseen 2025 player-games** before the final framework was refit using 2023–2025 data.

| Market | 2025 test projections | Model MAE | Trailing-3 MAE | Improvement |
|---|---:|---:|---:|---:|
| Passing yards | 402 | 62.11 | 69.79 | **11.0%** |
| Rushing yards | 577 | 27.08 | 29.66 | **8.7%** |
| Receiving yards | 1,210 | 26.08 | 28.18 | **7.4%** |

Across **2,189 holdout projections**, the model improved on the trailing-3 baseline in all three markets.

> MAE is measured in yards, so results should be interpreted within each market rather than compared directly across passing, rushing, and receiving.

## From backtest to forward projections

The first version trained on **2023 regular-season data** and evaluated on **unseen 2024 player-games**. That stage established the core workflow: time-aware feature creation, leakage prevention, benchmark comparison, out-of-sample evaluation, and manual-review flags.

### [View the original historical backtest dashboard](https://scyoung2004-design.github.io/nfl-prematch-projection-engine/backtesting.html)

The current version extends that framework:

1. Develop models using 2023–2024 history.
2. Validate on unseen 2025 player-games.
3. Compare against a trailing-3 recent-form baseline.
4. Refit using 2023–2025 history.
5. Generate 2026 Week 1 projections for eligible returning players.

## 2026 Week 1 dashboard

The live portfolio dashboard includes featured Week 1 projections with filters for market, risk level, player, and team.

Each row shows:

- model projection
- trailing-3 and trailing-5 averages
- recent workload
- opponent trailing-5 yards allowed
- available historical games
- manual-review risk level

The dashboard is a **decision-support demonstration, not a wagering recommendation**.

## Game Operations risk layer

Model output is not treated as automatically safe. Each projection receives a review flag based primarily on:

- **model vs. recent-form disagreement**
- **recent player volatility**

Rows are labeled **LOW, MEDIUM, or HIGH** risk.

A HIGH-risk label does not imply a player should go over or under. It means the estimate deserves additional analyst review for factors such as injuries, depth-chart changes, expected snaps, weather, and late-breaking news.

## Modeling approach

Ridge regression was selected because recent-performance and workload features are naturally correlated. Regularization helps stabilize the model while keeping it interpretable.

Core features include:

- previous-game production
- trailing 3-, 5-, and longer-history averages
- recent attempts, carries, or targets
- opponent recent yards allowed to the relevant position group

Eligibility is based on prior workload so projections focus on players with enough recent usage and history to support a meaningful estimate.

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
├── docs/
│   ├── index.html
│   └── backtesting.html
└── assets/
    ├── holdout_mae_comparison.png
    ├── weekly_mae_passing_yards.png
    ├── weekly_mae_rushing_yards.png
    └── weekly_mae_receiving_yards.png
```

The files in `outputs/` and `assets/` preserve the historical backtest artifacts. `docs/index.html` powers the forward-looking 2026 dashboard, while `docs/backtesting.html` preserves the original backtest dashboard.

## Run the historical pipeline

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/build_project.py
```

The pipeline rebuilds historical features, trains the models, evaluates holdout performance, writes CSV outputs, generates a local SQLite database, creates charts, and rebuilds the historical dashboard. The generated database is not tracked in the repository.

## SQL layer

`sql/analysis_queries.sql` supports questions such as:

- Which market improved most over the baseline?
- Which weeks had the highest model error?
- Which projections should enter a manual review queue?
- Where does the model disagree most with recent form?

## Current limitations

The 2026 board does not yet incorporate every input a production Game Operations team would use, including:

- real-time injuries and practice status
- confirmed depth charts and expected snaps
- weather
- late-breaking news
- market movement
- manual sport-owner adjustments

These are natural next steps for improving both projection accuracy and the risk-review process.

## Data and attribution

Historical NFL data comes from the public `NityaGehlot/nfl-data` repository, whose documented pipeline derives player statistics from `nflreadr` / nflverse.

- https://github.com/NityaGehlot/nfl-data
- https://github.com/nflverse/nflverse-data
- https://www.prizepicks.com/help-center/player-picks

See `ATTRIBUTION.md` for additional details.

## Key takeaway

This project demonstrates a complete analytics workflow: **build a model, validate it on unseen data, benchmark it against a simple heuristic, identify operational risk, and use the validated framework to produce forward-looking projections.**

The goal is not perfect forecasting. It is a transparent, reusable decision-support process that improves on recent-form heuristics while clearly identifying cases that deserve human review.
