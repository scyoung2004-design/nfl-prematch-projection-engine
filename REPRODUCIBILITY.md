# Reproducibility

This repository separates **published snapshots** from **live regeneration** so the portfolio result is both reviewable and reproducible.

## Published dashboard snapshot

The values currently shown on the 2026 Week 1 GitHub Pages dashboard are preserved in:

- `outputs/2026_week1_featured_board.csv`
- `outputs/2025_validation_metrics.csv`

These files provide a fixed record of the published portfolio result.

## Rebuild from public data

To rebuild the forward-looking pipeline:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/build_live_2026.py
```

The script:

1. downloads 2023, 2024, and 2025 weekly player data;
2. develops ridge models on pooled 2023-2024 player-game examples;
3. validates the models on unseen 2025 player-games;
4. refits the projection framework on pooled 2023-2025 examples;
5. downloads the 2026 nflverse roster and schedule;
6. creates Week 1 projections for returning players who meet prior-usage thresholds;
7. writes the full board, featured board, review queue, omitted-player reasons, validation metrics, and HTML dashboard.

Generated files include:

- `outputs/2025_validation_metrics.csv`
- `outputs/2026_week1_projection_board.csv`
- `outputs/2026_week1_featured_board.csv`
- `outputs/2026_week1_review_queue.csv`
- `outputs/2026_week1_unprojected.csv`
- `dashboard/index.html`
- `docs/index.html`

## Why a rerun can differ from the published snapshot

The 2026 roster is a live upstream data source and can change as players are signed, released, traded, or moved between roster statuses. A future rerun may therefore produce a different eligible Week 1 board even when the modeling code is unchanged.

That is why the repository keeps the published CSV snapshot alongside the regeneration script.

Historical backtesting artifacts remain separately available through `src/build_project.py`, `outputs/`, `assets/`, and `docs/backtesting.html`.

## Leakage control

For historical validation, each player-week feature row is built before that week's outcome is added to the player's or opponent's history. The 2025 validation set is not used to fit the 2023-2024 validation models.

The final 2026 projection framework is refit only after validation is complete.
