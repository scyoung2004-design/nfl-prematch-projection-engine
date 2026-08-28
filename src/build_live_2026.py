"""Rebuild the forward-looking 2026 Week 1 NFL projection board.

This script is the reproducible companion to the published GitHub Pages dashboard.

Workflow
--------
1. Download 2023, 2024, and 2025 weekly NFL player data.
2. Develop the ridge models on pooled 2023-2024 examples.
3. Validate on unseen 2025 player-games.
4. Refit on pooled 2023-2025 examples.
5. Download the 2026 nflverse season roster and schedule.
6. Generate Week 1 projections for returning players who meet prior-usage thresholds.
7. Write CSV outputs plus the dashboard used by GitHub Pages.

The historical feature builder is imported from build_project.py.  For the live
model we intentionally remove the normalized week-index feature so Week 1 is not
given an artificial effect simply because historical examples begin after a
player accumulates prior games.

This is an independent portfolio project. It does not use PrizePicks proprietary
data or attempt to reproduce PrizePicks internal projections.
"""

from __future__ import annotations

import io
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import requests

import build_project as bp

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DASHBOARD = ROOT / "dashboard"
DOCS = ROOT / "docs"

DEV_YEARS = [2023, 2024]
VALIDATION_YEAR = 2025
PROJECTION_YEAR = 2026
PROJECTION_WEEK = 1

LIVE_FEATURES = [
    "lag1",
    "avg3",
    "avg5",
    "avg8",
    "volume_avg3",
    "volume_avg5",
    "opponent_allowed_avg5",
]

SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "schedules/games.csv"
)
ROSTER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "rosters/roster_2026.csv"
)

TEAM_ALIASES = {
    "JAC": "JAX",
    "LAR": "LA",
    "STL": "LA",
    "WSH": "WAS",
    "SD": "LAC",
    "OAK": "LV",
}


def normalize_team(value: object) -> str:
    team = str(value).strip().upper()
    return TEAM_ALIASES.get(team, team)


def remote_csv(url: str) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": "nfl-projection-portfolio/1.0"})
    response = session.get(url, timeout=90)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.text))


def matchup_map() -> Dict[str, str]:
    games = remote_csv(SCHEDULE_URL)
    required = {"season", "week", "home_team", "away_team"}
    missing = required.difference(games.columns)
    if missing:
        raise ValueError(f"Schedule is missing columns: {sorted(missing)}")

    mask = (
        pd.to_numeric(games["season"], errors="coerce").eq(PROJECTION_YEAR)
        & pd.to_numeric(games["week"], errors="coerce").eq(PROJECTION_WEEK)
    )
    if "game_type" in games.columns:
        mask &= games["game_type"].astype(str).eq("REG")

    week = games.loc[mask].copy()
    if week.empty:
        raise RuntimeError(
            f"No {PROJECTION_YEAR} Week {PROJECTION_WEEK} games were found in the "
            "nflverse schedule release."
        )

    out: Dict[str, str] = {}
    for row in week.itertuples():
        home = normalize_team(row.home_team)
        away = normalize_team(row.away_team)
        out[home] = away
        out[away] = home
    return out


def current_roster() -> pd.DataFrame:
    roster = remote_csv(ROSTER_URL)

    def choose(candidates: List[str]) -> str:
        for col in candidates:
            if col in roster.columns:
                return col
        raise ValueError(f"Roster is missing one of these columns: {candidates}")

    id_col = choose(["gsis_id", "player_id"])
    team_col = choose(["team"])
    pos_col = choose(["position", "pos"])
    name_col = choose(["full_name", "player_name", "football_name", "display_name"])

    out = roster[[id_col, name_col, team_col, pos_col]].copy()
    out.columns = ["player_id", "roster_name", "team", "position"]
    out["player_id"] = out["player_id"].astype(str).str.strip()
    out["team"] = out["team"].map(normalize_team)
    out["position"] = out["position"].astype(str).str.upper().str.strip()
    out = out[
        out["player_id"].ne("")
        & out["player_id"].ne("nan")
        & out["team"].ne("")
        & out["team"].ne("NAN")
    ]
    return out.drop_duplicates("player_id", keep="last")


def build_histories(
    weekly_data: Dict[int, pd.DataFrame], market: str
) -> tuple[Dict[str, List[dict]], Dict[str, List[float]]]:
    cfg = bp.MARKETS[market]
    player_history: Dict[str, List[dict]] = defaultdict(list)
    defense_history: Dict[str, List[float]] = defaultdict(list)

    for week in sorted(weekly_data):
        df = weekly_data[week]
        if df.empty:
            continue

        rows = df[df["position"].isin(cfg["positions"])].to_dict("records")

        for row in rows:
            player_id = row.get("player_id")
            if not player_id:
                continue
            player_history[str(player_id)].append(
                {
                    "target": float(row.get(cfg["target"], 0) or 0),
                    "volume": float(row.get(cfg["volume"], 0) or 0),
                    "player_name": row.get("player_name"),
                    "position": row.get("position"),
                    "team": normalize_team(row.get("team")),
                    "week": week,
                }
            )

        allowed: Dict[str, float] = defaultdict(float)
        for row in rows:
            opponent = row.get("opponent_team")
            if opponent:
                allowed[normalize_team(opponent)] += float(
                    row.get(cfg["target"], 0) or 0
                )
        for defense, value in allowed.items():
            defense_history[defense].append(value)

    return player_history, defense_history


def live_feature_row(
    history: List[dict],
    opponent_history: List[float],
) -> tuple[List[float], float, float, float, float]:
    h3 = history[-3:]
    h5 = history[-5:]
    h8 = history[-8:]

    recent3 = bp.mean(x["target"] for x in h3)
    recent5 = bp.mean(x["target"] for x in h5)
    volume3 = bp.mean(x["volume"] for x in h3)
    volume5 = bp.mean(x["volume"] for x in h5)
    opponent5 = bp.mean(opponent_history[-5:]) if opponent_history else 0.0

    features = [
        h3[-1]["target"],
        recent3,
        recent5,
        bp.mean(x["target"] for x in h8),
        volume3,
        volume5,
        opponent5,
    ]
    return features, recent3, recent5, volume3, opponent5


def project_row(features: List[float], model: dict) -> float:
    x = np.asarray(features, dtype=float)
    z = (x - model["means"]) / model["sds"]
    z = np.r_[1.0, z]
    return max(0.0, float(z @ model["beta"]))


def risk_fields(
    projection: float,
    recent3: float,
    recent_sd: float,
    model: dict,
) -> tuple[float, str, str]:
    residual_sd = max(float(model["residual_sd"]), 1e-9)
    score = abs(projection - recent3) / residual_sd + 0.65 * recent_sd / residual_sd
    if score >= 1.35:
        return score, "HIGH", "Low"
    if score >= 0.85:
        return score, "MEDIUM", "Medium"
    return score, "LOW", "High"


def validation_metrics(
    season_examples: Dict[int, Dict[str, pd.DataFrame]]
) -> pd.DataFrame:
    rows: List[dict] = []
    for market in bp.MARKETS:
        train = pd.concat(
            [season_examples[y][market] for y in DEV_YEARS],
            ignore_index=True,
        )
        test = season_examples[VALIDATION_YEAR][market]
        model = bp.fit_ridge(train)
        scored = bp.apply_model(test, model)
        rows.append(bp.performance_row(market, scored))
    return pd.DataFrame(rows)


def build_forward_board(
    season_examples: Dict[int, Dict[str, pd.DataFrame]],
    validation_weeks: Dict[int, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    roster = current_roster()
    opponents = matchup_map()

    board_rows: List[dict] = []
    omitted_rows: List[dict] = []

    for market, cfg in bp.MARKETS.items():
        full_train = pd.concat(
            [season_examples[y][market] for y in [2023, 2024, 2025]],
            ignore_index=True,
        )
        model = bp.fit_ridge(full_train)
        player_history, defense_history = build_histories(validation_weeks, market)

        supported_positions = set(cfg["positions"])
        market_roster = roster[roster["position"].isin(supported_positions)]

        for rr in market_roster.itertuples(index=False):
            player_id = str(rr.player_id)
            history = player_history.get(player_id, [])
            reason = None

            if not history:
                reason = "no_2025_supported_market_history"
            elif len(history) < 3:
                reason = "fewer_than_3_2025_games"
            elif rr.team not in opponents:
                reason = "no_week1_matchup"

            if reason is not None:
                omitted_rows.append(
                    {
                        "market": market,
                        "player_id": player_id,
                        "player": rr.roster_name,
                        "position": rr.position,
                        "team": rr.team,
                        "reason": reason,
                    }
                )
                continue

            opponent = opponents[rr.team]
            features, recent3, recent5, volume3, opponent5 = live_feature_row(
                history, defense_history.get(opponent, [])
            )

            if volume3 < float(cfg["min_avg3_volume"]):
                omitted_rows.append(
                    {
                        "market": market,
                        "player_id": player_id,
                        "player": rr.roster_name,
                        "position": rr.position,
                        "team": rr.team,
                        "reason": "below_prior_usage_threshold",
                    }
                )
                continue

            projection = project_row(features, model)
            recent_sd = bp.sample_sd(x["target"] for x in history[-5:])
            risk_score, risk, confidence = risk_fields(
                projection, recent3, recent_sd, model
            )

            last_name = history[-1].get("player_name") or rr.roster_name
            board_rows.append(
                {
                    "market": market,
                    "player_id": player_id,
                    "player": last_name,
                    "position": rr.position,
                    "team": rr.team,
                    "opponent": opponent,
                    "projection": round(projection, 1),
                    "recent_avg3": round(recent3, 1),
                    "recent_avg5": round(recent5, 1),
                    "volume_avg3": round(volume3, 1),
                    "opponent_allowed_avg5": round(opponent5, 1),
                    "recent_sd": round(recent_sd, 1),
                    "risk_score": round(risk_score, 3),
                    "risk": risk,
                    "confidence": confidence,
                    "history_games": len(history),
                }
            )

    board = pd.DataFrame(board_rows)
    if not board.empty:
        board = board.sort_values(
            ["market", "projection"], ascending=[True, False]
        ).reset_index(drop=True)

    omitted = pd.DataFrame(omitted_rows)
    return board, omitted


def display_market(market: str) -> str:
    return market.replace("_yards", "").replace("_", " ").title() + " Yards"


def render_dashboard(featured: pd.DataFrame, metrics: pd.DataFrame) -> str:
    data_json = json.dumps(featured.to_dict("records"))
    metrics_json = json.dumps(metrics.to_dict("records"))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NFL 2026 Week 1 Projection Dashboard</title>
<style>
:root{{--bg:#f5f7fb;--card:#fff;--text:#172033;--muted:#667085;--line:#e4e7ec}}
*{{box-sizing:border-box}} body{{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text)}}
.wrap{{max-width:1280px;margin:auto;padding:34px 24px 60px}} h1{{font-size:30px;margin:0 0 8px}} .sub{{color:var(--muted);max-width:900px;line-height:1.5}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}} .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(16,24,40,.04)}}
.big{{font-size:28px;font-weight:750;margin-top:5px}} .small{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
.controls{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}} select,input{{border:1px solid var(--line);background:white;border-radius:9px;padding:10px 12px;font-size:14px}}
.tablebox{{background:white;border:1px solid var(--line);border-radius:14px;overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:950px}} th,td{{padding:12px 13px;border-bottom:1px solid var(--line);text-align:right;font-size:13px}} th{{background:#f9fafb;color:#475467;font-size:11px;text-transform:uppercase;letter-spacing:.04em;position:sticky;top:0}} th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3),th:nth-child(4),td:nth-child(4){{text-align:left}}
.pill{{display:inline-block;padding:4px 8px;border-radius:999px;border:1px solid var(--line);font-weight:700;font-size:11px}} .HIGH{{background:#fff1f0}} .MEDIUM{{background:#fff7e6}} .LOW{{background:#ecfdf3}}
.note{{font-size:12px;color:var(--muted);margin-top:12px;line-height:1.5}} .section{{margin-top:30px}} .barrow{{display:grid;grid-template-columns:145px 1fr 85px;gap:10px;align-items:center;margin:10px 0}} .track{{height:16px;background:#eef1f5;border-radius:99px;overflow:hidden}} .fill{{height:100%;background:#667085;border-radius:99px}} @media(max-width:760px){{.cards{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>NFL 2026 Week 1 Pre-Match Projection Board</h1>
<div class="sub">Forward-looking portfolio estimates built from 2023-2025 NFL history. Validation models are trained on pooled 2023-2024 player-games and tested on unseen 2025 player-games before final refitting. Risk indicates <b>manual-review priority</b>, not expected player performance.</div>
<div class="cards" id="cards"></div>
<div class="section"><h2>Featured Week 1 board</h2><div class="controls">
<select id="market"><option value="all">All markets</option><option value="passing_yards">Passing yards</option><option value="rushing_yards">Rushing yards</option><option value="receiving_yards">Receiving yards</option></select>
<select id="risk"><option value="all">All risk levels</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select>
<input id="search" placeholder="Search player or team">
</div><div class="tablebox"><table><thead><tr><th>Market</th><th>Player</th><th>Matchup</th><th>Risk</th><th>Projection</th><th>Recent 3</th><th>Recent 5</th><th>Recent workload</th><th>Opp allowed 5</th><th>History games</th></tr></thead><tbody id="tbody"></tbody></table></div>
<div class="note">The dashboard shows the top 10 projected rows per market. The full eligible board, review queue, and omitted-player reasons are written to <code>outputs/</code> when <code>python src/build_live_2026.py</code> is run.</div></div>
<div class="section"><h2>2025 validation improvement vs trailing-3 baseline</h2><div id="bars"></div><div class="note">MAE is measured in yards, so values are interpreted within each market rather than compared directly across markets.</div></div>
<div class="section"><div class="card"><b>Operational interpretation</b><div class="note">A HIGH-risk row is not a recommendation to take More or Less. It means recent volatility and/or model disagreement is large enough that an analyst should investigate injury status, role, depth chart, expected snaps, weather, and late news before relying on the estimate.</div></div></div>
</div>
<script>
const data={data_json}; const metrics={metrics_json};
const fmt=m=>m.replace('_yards','').replace('_',' ')+' yards';
function cards(){{document.getElementById('cards').innerHTML=metrics.map(m=>`<div class="card"><div class="small">${{fmt(m.market)}} • 2025 holdout</div><div class="big">${{Number(m.mae_improvement_pct).toFixed(1)}}% better</div><div class="note">MAE ${{Number(m.mae).toFixed(2)}} vs ${{Number(m.baseline_mae).toFixed(2)}} baseline • n=${{Number(m.test_n).toLocaleString()}}</div></div>`).join('')}}
function render(){{const mk=document.getElementById('market').value,rk=document.getElementById('risk').value,q=document.getElementById('search').value.toLowerCase();const d=data.filter(r=>(mk==='all'||r.market===mk)&&(rk==='all'||r.risk===rk)&&(!q||r.player.toLowerCase().includes(q)||r.team.toLowerCase().includes(q)||r.opponent.toLowerCase().includes(q)));document.getElementById('tbody').innerHTML=d.map(r=>`<tr><td>${{fmt(r.market)}}</td><td><b>${{r.player}}</b><br><span style="color:#667085">${{r.position}}</span></td><td>${{r.team}} vs ${{r.opponent}}</td><td><span class="pill ${{r.risk}}">${{r.risk}}</span></td><td><b>${{Number(r.projection).toFixed(1)}}</b></td><td>${{Number(r.recent_avg3).toFixed(1)}}</td><td>${{Number(r.recent_avg5).toFixed(1)}}</td><td>${{Number(r.volume_avg3).toFixed(1)}}</td><td>${{Number(r.opponent_allowed_avg5).toFixed(1)}}</td><td>${{r.history_games}}</td></tr>`).join('')}}
function bars(){{const max=Math.max(...metrics.map(m=>Number(m.mae_improvement_pct)));document.getElementById('bars').innerHTML=metrics.map(m=>`<div class="barrow"><div>${{fmt(m.market)}}</div><div class="track"><div class="fill" style="width:${{Number(m.mae_improvement_pct)/max*100}}%"></div></div><b>${{Number(m.mae_improvement_pct).toFixed(1)}}%</b></div>`).join('')}}
['market','risk','search'].forEach(id=>document.getElementById(id).addEventListener(id==='search'?'input':'change',render));cards();bars();render();
</script></body></html>"""


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    # Reuse the historical feature code, but omit week_index for the live model.
    bp.FEATURE_NAMES = LIVE_FEATURES

    all_weeks: Dict[int, Dict[int, pd.DataFrame]] = {}
    season_examples: Dict[int, Dict[str, pd.DataFrame]] = {}

    for year in [2023, 2024, 2025]:
        print(f"\nLoading {year}...")
        all_weeks[year] = bp.load_season(year)
        season_examples[year] = {
            market: bp.build_examples(all_weeks[year], market)
            for market in bp.MARKETS
        }

    metrics = validation_metrics(season_examples)
    board, omitted = build_forward_board(
        season_examples,
        all_weeks[VALIDATION_YEAR],
    )

    featured = (
        board.sort_values(["market", "projection"], ascending=[True, False])
        .groupby("market", group_keys=False)
        .head(10)
        .reset_index(drop=True)
    )
    review = board[board["risk"].isin(["HIGH", "MEDIUM"])].copy()

    metrics.to_csv(OUTPUTS / "2025_validation_metrics.csv", index=False)
    board.to_csv(OUTPUTS / "2026_week1_projection_board.csv", index=False)
    featured.to_csv(OUTPUTS / "2026_week1_featured_board.csv", index=False)
    review.to_csv(OUTPUTS / "2026_week1_review_queue.csv", index=False)
    omitted.to_csv(OUTPUTS / "2026_week1_unprojected.csv", index=False)

    html = render_dashboard(featured, metrics)
    (DASHBOARD / "index.html").write_text(html, encoding="utf-8")
    (DOCS / "index.html").write_text(html, encoding="utf-8")

    print("\n2025 validation")
    print(metrics.to_string(index=False))
    print(f"\nEligible Week 1 projections: {len(board):,}")
    print(f"Featured dashboard rows: {len(featured):,}")
    print(f"Manual-review rows: {len(review):,}")
    print(f"Omitted supported-position roster rows: {len(omitted):,}")
    print(f"\nOutputs written to {OUTPUTS}")


if __name__ == "__main__":
    main()
