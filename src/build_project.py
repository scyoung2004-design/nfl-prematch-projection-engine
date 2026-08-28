"""NFL Pre-Match Player Projection & Game Operations Dashboard.

Portfolio project built for sports analytics / game operations roles.

The pipeline:
1. Downloads public weekly NFL player data from a GitHub-hosted nflverse-derived archive.
2. Builds leakage-safe rolling features using only information available before each game.
3. Fits a ridge-regression projection model on one season.
4. Backtests on a later season.
5. Compares model MAE against a simple trailing-3-game baseline.
6. Creates risk flags, CSV outputs, a SQLite database, charts, and an HTML dashboard.

This is an independent educational project. It does not use PrizePicks proprietary data
or attempt to reproduce PrizePicks' internal pricing/projection methodology.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
ASSETS = ROOT / "assets"
DASHBOARD = ROOT / "dashboard"

TRAIN_YEAR = 2023
TEST_YEAR = 2024
REGULAR_SEASON_WEEKS = list(range(1, 19))
RIDGE_LAMBDA = 3.0

FEATURE_NAMES = [
    "lag1",
    "avg3",
    "avg5",
    "avg8",
    "volume_avg3",
    "volume_avg5",
    "opponent_allowed_avg5",
    "week_index",
]

MARKETS = {
    "passing_yards": {
        "positions": {"QB"},
        "target": "passing_yards",
        "volume": "attempts",
        "min_avg3_volume": 20.0,
    },
    "rushing_yards": {
        "positions": {"RB"},
        "target": "rushing_yards",
        "volume": "carries",
        "min_avg3_volume": 7.0,
    },
    "receiving_yards": {
        "positions": {"WR", "TE"},
        "target": "receiving_yards",
        "volume": "targets",
        "min_avg3_volume": 4.0,
    },
}


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return float(np.mean(vals)) if vals else 0.0


def sample_sd(values: Iterable[float]) -> float:
    vals = list(values)
    return float(np.std(vals, ddof=1)) if len(vals) >= 2 else 0.0


def last(values: List[dict], n: int) -> List[dict]:
    return values[-n:]


def source_url(year: int, week: int) -> str:
    week_str = f"{week:02d}"
    return (
        "https://raw.githubusercontent.com/NityaGehlot/nfl-data/main/"
        f"data/Stats/{year}%20Season/{year}%20Offense/"
        f"player_stats_{year}_week{week_str}.json"
    )


def fetch_week(session: requests.Session, year: int, week: int) -> pd.DataFrame:
    url = source_url(year, week)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()

    # Historical files are keyed objects whose values are one-row arrays.
    if isinstance(payload, dict):
        rows = [row for group in payload.values() for row in group]
    elif isinstance(payload, list):
        rows = payload
    else:
        raise ValueError(f"Unexpected payload type for {year} week {week}: {type(payload)}")

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    played = df.get("game_played", False).fillna(False).astype(bool)
    season_present = df.get("season").notna()
    return df.loc[played & season_present].copy()


def load_season(year: int) -> Dict[int, pd.DataFrame]:
    session = requests.Session()
    session.headers.update({"User-Agent": "nfl-projection-portfolio/1.0"})
    weeks: Dict[int, pd.DataFrame] = {}
    for week in REGULAR_SEASON_WEEKS:
        print(f"Downloading {year} week {week:02d}...")
        weeks[week] = fetch_week(session, year, week)
    return weeks


def build_examples(weekly_data: Dict[int, pd.DataFrame], market: str) -> pd.DataFrame:
    cfg = MARKETS[market]
    player_history: Dict[str, List[dict]] = defaultdict(list)
    defense_history: Dict[str, List[float]] = defaultdict(list)
    examples: List[dict] = []

    for week in sorted(weekly_data):
        df = weekly_data[week]
        if df.empty:
            continue
        rows = df[df["position"].isin(cfg["positions"])].to_dict("records")

        # Generate features BEFORE updating histories for the current week.
        for row in rows:
            player_id = row.get("player_id")
            opponent = row.get("opponent_team")
            if not player_id or not opponent:
                continue

            ph = player_history[player_id]
            dh = defense_history[opponent]
            if len(ph) < 3:
                continue

            h3, h5, h8 = last(ph, 3), last(ph, 5), last(ph, 8)
            avg_vol3 = mean(x["volume"] for x in h3)
            if avg_vol3 < cfg["min_avg3_volume"]:
                continue

            features = [
                h3[-1]["target"],
                mean(x["target"] for x in h3),
                mean(x["target"] for x in h5),
                mean(x["target"] for x in h8),
                avg_vol3,
                mean(x["volume"] for x in h5),
                mean(dh[-5:]) if dh else 0.0,
                week / 18.0,
            ]

            examples.append(
                {
                    "week": week,
                    "player_id": player_id,
                    "player_name": row.get("player_name"),
                    "position": row.get("position"),
                    "team": row.get("team"),
                    "opponent": opponent,
                    "actual": float(row.get(cfg["target"], 0) or 0),
                    "current_volume": float(row.get(cfg["volume"], 0) or 0),
                    "baseline": features[1],
                    "recent_sd": sample_sd(x["target"] for x in h5),
                    **{name: value for name, value in zip(FEATURE_NAMES, features)},
                }
            )

        # Update player histories after examples are created.
        for row in rows:
            player_id = row.get("player_id")
            if not player_id:
                continue
            player_history[player_id].append(
                {
                    "target": float(row.get(cfg["target"], 0) or 0),
                    "volume": float(row.get(cfg["volume"], 0) or 0),
                }
            )

        # Aggregate market yards allowed by defense for this position group.
        allowed_this_week: Dict[str, float] = defaultdict(float)
        for row in rows:
            opponent = row.get("opponent_team")
            if opponent:
                allowed_this_week[opponent] += float(row.get(cfg["target"], 0) or 0)
        for defense, value in allowed_this_week.items():
            defense_history[defense].append(value)

    result = pd.DataFrame(examples)
    if not result.empty:
        result.insert(0, "market", market)
    return result


def fit_ridge(train: pd.DataFrame) -> dict:
    X = train[FEATURE_NAMES].astype(float).to_numpy()
    y = train["actual"].astype(float).to_numpy()

    means = X.mean(axis=0)
    sds = X.std(axis=0, ddof=1)
    sds = np.where(sds == 0, 1.0, sds)
    Z = (X - means) / sds
    Z = np.column_stack([np.ones(len(Z)), Z])

    penalty = np.eye(Z.shape[1]) * RIDGE_LAMBDA
    penalty[0, 0] = 0.0  # do not penalize intercept
    beta = np.linalg.solve(Z.T @ Z + penalty, Z.T @ y)

    pred = np.maximum(0, Z @ beta)
    residual_sd = float(np.std(y - pred, ddof=1))
    return {
        "means": means,
        "sds": sds,
        "beta": beta,
        "residual_sd": residual_sd,
    }


def apply_model(test: pd.DataFrame, model: dict) -> pd.DataFrame:
    scored = test.copy()
    X = scored[FEATURE_NAMES].astype(float).to_numpy()
    Z = (X - model["means"]) / model["sds"]
    Z = np.column_stack([np.ones(len(Z)), Z])
    scored["projection"] = np.maximum(0, Z @ model["beta"])
    scored["error"] = scored["actual"] - scored["projection"]
    scored["abs_error"] = scored["error"].abs()

    residual_sd = max(model["residual_sd"], 1e-9)
    scored["risk_score"] = (
        (scored["projection"] - scored["baseline"]).abs() / residual_sd
        + 0.65 * scored["recent_sd"] / residual_sd
    )
    scored["risk"] = pd.cut(
        scored["risk_score"],
        bins=[-np.inf, 0.85, 1.35, np.inf],
        labels=["LOW", "MEDIUM", "HIGH"],
    ).astype(str)
    scored["confidence"] = scored["risk"].map(
        {"LOW": "High", "MEDIUM": "Medium", "HIGH": "Low"}
    )
    return scored


def performance_row(market: str, scored: pd.DataFrame) -> dict:
    mae = float(scored["abs_error"].mean())
    rmse = float(np.sqrt(np.mean(scored["error"] ** 2)))
    baseline_mae = float((scored["actual"] - scored["baseline"]).abs().mean())
    improvement = (baseline_mae - mae) / baseline_mae * 100 if baseline_mae else 0.0
    return {
        "market": market,
        "test_n": len(scored),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "bias": round(float((scored["projection"] - scored["actual"]).mean()), 2),
        "baseline_mae": round(baseline_mae, 2),
        "mae_improvement_pct": round(improvement, 1),
    }


def create_sqlite(
    model_metrics: pd.DataFrame,
    weekly_metrics: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    db_path = OUTPUTS / "nfl_projection.db"
    with sqlite3.connect(db_path) as conn:
        model_metrics.to_sql("model_performance", conn, if_exists="replace", index=False)
        weekly_metrics.to_sql("weekly_performance", conn, if_exists="replace", index=False)
        predictions.to_sql("backtest_predictions", conn, if_exists="replace", index=False)
        predictions[predictions["week"] == 18].to_sql(
            "projection_board_week18", conn, if_exists="replace", index=False
        )


def create_charts(model_metrics: pd.DataFrame, weekly_metrics: pd.DataFrame) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    # Holdout MAE comparison.
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(model_metrics))
    width = 0.36
    ax.bar(x - width / 2, model_metrics["baseline_mae"], width, label="3-game baseline")
    ax.bar(x + width / 2, model_metrics["mae"], width, label="Ridge model")
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("_", " ").title() for m in model_metrics["market"]])
    ax.set_ylabel("Mean Absolute Error")
    ax.set_title("2024 Holdout Error: Model vs. Recent-Form Baseline")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ASSETS / "holdout_mae_comparison.png", dpi=180)
    plt.close(fig)

    # Weekly performance by market.
    for market, group in weekly_metrics.groupby("market"):
        fig, ax = plt.subplots(figsize=(9, 5.5))
        ax.plot(group["week"], group["mae"], marker="o", label="Ridge model")
        ax.plot(group["week"], group["baseline_mae"], marker="o", label="3-game baseline")
        ax.set_xlabel("NFL Week")
        ax.set_ylabel("Mean Absolute Error")
        ax.set_title(f"Weekly Holdout Error — {market.replace('_', ' ').title()}")
        ax.set_xticks(sorted(group["week"].unique()))
        ax.grid(alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(ASSETS / f"weekly_mae_{market}.png", dpi=180)
        plt.close(fig)


def create_dashboard(model_metrics: pd.DataFrame, board: pd.DataFrame) -> None:
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    metric_cards = "".join(
        f"""
        <div class='card'>
          <h3>{row.market.replace('_',' ').title()}</h3>
          <div class='big'>{row.mae:.2f} MAE</div>
          <div class='sub'>{row.mae_improvement_pct:.1f}% better than trailing-3 baseline</div>
          <div class='sub'>{int(row.test_n)} holdout projections</div>
        </div>
        """
        for row in model_metrics.itertuples()
    )

    board_cols = [
        "market", "player_name", "position", "team", "opponent", "projection",
        "baseline", "actual", "abs_error", "confidence", "risk"
    ]
    table_rows = []
    for row in board[board_cols].itertuples(index=False):
        risk_class = str(row.risk).lower()
        table_rows.append(
            "<tr "
            f"data-market='{row.market}'>"
            f"<td>{row.market.replace('_',' ')}</td>"
            f"<td>{row.player_name}</td><td>{row.position}</td><td>{row.team}</td>"
            f"<td>{row.opponent}</td><td>{row.projection:.1f}</td>"
            f"<td>{row.baseline:.1f}</td><td>{row.actual:.1f}</td>"
            f"<td>{row.abs_error:.1f}</td><td>{row.confidence}</td>"
            f"<td><span class='pill {risk_class}'>{row.risk}</span></td></tr>"
        )

    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>NFL Pre-Match Projection Dashboard</title>
<style>
:root {{ --bg:#0e1117; --panel:#171b24; --text:#eef2f7; --muted:#9aa4b2; --line:#2a3140; }}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,Arial,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:32px 20px 60px}} h1{{margin:0 0 8px;font-size:34px}}
.lede{{color:var(--muted);max-width:850px;line-height:1.5;margin-bottom:24px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:26px}} .card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}
.card h3{{margin:0 0 14px;font-size:16px}} .big{{font-size:26px;font-weight:700;margin-bottom:7px}} .sub{{color:var(--muted);font-size:13px;margin-top:4px}}
.controls{{display:flex;gap:12px;align-items:center;margin:18px 0}} select,input{{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:9px 11px}}
.tablewrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}} table{{width:100%;border-collapse:collapse;background:var(--panel);font-size:13px}} th,td{{padding:11px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}} th{{position:sticky;top:0;background:#202633}}
.pill{{padding:4px 8px;border-radius:999px;font-weight:700;font-size:11px}} .low{{background:#183c2c}} .medium{{background:#4a3a16}} .high{{background:#4b2026}}
.note{{color:var(--muted);font-size:12px;margin-top:14px;line-height:1.5}} @media(max-width:800px){{.cards{{grid-template-columns:1fr}}}}
</style>
</head>
<body><div class='wrap'>
<h1>NFL Pre-Match Projection & Game Operations Dashboard</h1>
<p class='lede'>Independent portfolio backtest. Ridge models are trained on 2023 regular-season data and evaluated on 2024 regular-season games using only pre-game rolling information. The comparison baseline is each player's trailing three-game average.</p>
<div class='cards'>{metric_cards}</div>
<h2>Week 18 Backtest Board</h2>
<div class='controls'>
<label>Market <select id='market'><option value='all'>All</option><option value='passing_yards'>Passing yards</option><option value='rushing_yards'>Rushing yards</option><option value='receiving_yards'>Receiving yards</option></select></label>
<label>Search <input id='search' placeholder='Player or team'></label>
</div>
<div class='tablewrap'><table><thead><tr><th>Market</th><th>Player</th><th>Pos</th><th>Team</th><th>Opp</th><th>Projection</th><th>Recent Avg</th><th>Actual</th><th>Abs Error</th><th>Confidence</th><th>Risk</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
<p class='note'>Risk is an operational review flag based on model-vs-baseline disagreement plus recent volatility. It is not a betting recommendation or a claim about PrizePicks' internal methodology. Week 18 is intentionally useful for discussion because rest/role changes create difficult edge cases that a production system should augment with injuries, depth charts, and news.</p>
</div>
<script>
const market=document.getElementById('market'), search=document.getElementById('search');
function filterRows(){{const m=market.value,q=search.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>{{const okM=m==='all'||r.dataset.market===m;const okQ=!q||r.innerText.toLowerCase().includes(q);r.style.display=(okM&&okQ)?'':'none';}})}}
market.addEventListener('change',filterRows);search.addEventListener('input',filterRows);
</script></body></html>"""
    (DASHBOARD / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    DASHBOARD.mkdir(parents=True, exist_ok=True)

    train_weeks = load_season(TRAIN_YEAR)
    test_weeks = load_season(TEST_YEAR)

    all_predictions: List[pd.DataFrame] = []
    metrics: List[dict] = []
    weekly_rows: List[dict] = []
    coefficient_rows: List[dict] = []

    for market in MARKETS:
        print(f"\nBuilding {market} model...")
        train = build_examples(train_weeks, market)
        test = build_examples(test_weeks, market)
        model = fit_ridge(train)
        scored = apply_model(test, model)

        metrics.append(performance_row(market, scored))
        all_predictions.append(scored)

        for week, group in scored.groupby("week"):
            weekly_rows.append(
                {
                    "market": market,
                    "week": int(week),
                    "n": len(group),
                    "mae": round(float(group["abs_error"].mean()), 2),
                    "baseline_mae": round(
                        float((group["actual"] - group["baseline"]).abs().mean()), 2
                    ),
                }
            )

        for feature, beta in zip(FEATURE_NAMES, model["beta"][1:]):
            coefficient_rows.append(
                {
                    "market": market,
                    "feature": feature,
                    "standardized_beta": round(float(beta), 4),
                }
            )

    model_metrics = pd.DataFrame(metrics)
    weekly_metrics = pd.DataFrame(weekly_rows).sort_values(["market", "week"])
    coefficients = pd.DataFrame(coefficient_rows)
    predictions = pd.concat(all_predictions, ignore_index=True)
    board = predictions[predictions["week"] == 18].copy()

    model_metrics.to_csv(OUTPUTS / "model_metrics.csv", index=False)
    weekly_metrics.to_csv(OUTPUTS / "weekly_metrics.csv", index=False)
    coefficients.to_csv(OUTPUTS / "model_coefficients.csv", index=False)
    predictions.to_csv(OUTPUTS / "backtest_predictions.csv", index=False)
    board.to_csv(OUTPUTS / "week18_projection_board.csv", index=False)

    create_sqlite(model_metrics, weekly_metrics, predictions)
    create_charts(model_metrics, weekly_metrics)
    create_dashboard(model_metrics, board)

    print("\n2024 holdout results")
    print(model_metrics.to_string(index=False))
    print(f"\nOutputs written to: {ROOT}")


if __name__ == "__main__":
    main()
