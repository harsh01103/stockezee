"""
PHASE O2 — TRADE READINESS OBSERVATION (NO CODE CHANGES)

Runs the full pipeline over captured session data in 5-minute observation windows.
Produces per-window metrics and a final summary decision.
"""
import glob
import os
import csv
import polars as pl
from datetime import datetime

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

from opportunities.scorer import score_opportunities
from opportunities.universe import build_universe
from opportunities.ranker import rank_opportunities
from opportunities.confidence import calculate_confidence


def build_composite(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    pk = ["underlying", "expiry", "strike", "option_type"]

    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)

    features = []
    if "vwoim_smoothed" in df.columns:
        df = df.with_columns(zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"))
        features.append("z_vwoim")
    if "oi_flow_score" in df.columns:
        df = df.with_columns(zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"))
        features.append("z_oi_flow")
    if "gex_proxy" in df.columns:
        df = df.with_columns(zscore("gex_proxy").fill_null(0).alias("z_gex"))
        features.append("z_gex")

    if not features:
        return df.with_columns(pl.lit(0.0).alias("composite_alpha_score"))

    df = df.with_columns(pl.sum_horizontal(features).alias("raw_score"))
    df = df.with_columns(
        (pl.col("raw_score") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    return df


def run_pipeline_snapshot(df_sig: pl.DataFrame, ts_val) -> pl.DataFrame:
    """Run scoring pipeline for a single timestamp slice."""
    df_ts = df_sig.filter(pl.col("timestamp") == ts_val)
    df_opp = build_universe(df_ts)
    df_opp = score_opportunities(df_opp)
    df_opp = rank_opportunities(df_opp)
    df_opp = calculate_confidence(df_opp)
    return df_opp


def main():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))

    if not raw_files:
        print("No raw data files found for", date_str)
        print("decision: INVESTIGATE")
        print("STOP")
        return

    # Load all raw data
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
    df_raw = pl.concat(dfs, how="diagonal_relaxed")

    # Build features + research
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    df_res = compute_gex_proxy(compute_regime_features(compute_vwoim(compute_oi_flow(df_feat))))
    df_res = df_res.sort("timestamp")

    # Build composite signal scores
    df_sig = build_composite(df_res)

    # Get all unique timestamps, sorted
    all_ts = sorted(df_sig["timestamp"].unique().to_list())
    if not all_ts:
        print("No timestamps found after feature build")
        print("decision: INVESTIGATE")
        print("STOP")
        return

    ts_min = all_ts[0]
    ts_max = all_ts[-1]
    session_duration_ms = ts_max - ts_min
    session_hours = session_duration_ms / (1000 * 3600)

    # Bucket timestamps into 5-minute windows (300_000 ms)
    window_ms = 300_000
    window_starts = []
    cur = ts_min
    while cur <= ts_max:
        window_starts.append(cur)
        cur += window_ms

    # Process each window cumulatively
    observation_rows = []
    global_peak = 0.0
    o1_peak = 0.6608  # From Phase O1
    peak_history = []  # (ts, peak) for rolling calculations
    all_candidates = []

    print(f"Session: {datetime.fromtimestamp(ts_min/1000).strftime('%H:%M:%S')} -> "
          f"{datetime.fromtimestamp(ts_max/1000).strftime('%H:%M:%S')} "
          f"({session_hours:.2f} hours)")
    print(f"Observation windows: {len(window_starts)}")
    print("-" * 100)

    for w_idx, w_start in enumerate(window_starts):
        w_end = w_start + window_ms

        # Get timestamps in this window
        window_ts = [t for t in all_ts if w_start <= t < w_end]
        if not window_ts:
            continue

        # Run pipeline for each timestamp in window
        window_candidates = []
        for ts_val in window_ts:
            df_opp = run_pipeline_snapshot(df_sig, ts_val)
            if not df_opp.is_empty() and "confidence" in df_opp.columns:
                window_candidates.append(df_opp)
                all_candidates.append(df_opp)

        if window_candidates:
            df_window = pl.concat(window_candidates, how="vertical_relaxed")
            cand_count = df_window.height
            peak_conf = float(df_window["confidence"].max())
            mean_conf = float(df_window["confidence"].mean())
            above_060 = df_window.filter(pl.col("confidence") > 0.60).height
            above_065 = df_window.filter(pl.col("confidence") > 0.65).height
            above_070 = df_window.filter(pl.col("confidence") > 0.70).height
            above_075 = df_window.filter(pl.col("confidence") > 0.75).height
            published = above_075

            # Winner (highest confidence in window)
            winner = df_window.sort("confidence", descending=True).head(1)
            w_underlying = winner["underlying"][0] if "underlying" in winner.columns else "N/A"
            w_expiry = str(winner["expiry"][0]) if "expiry" in winner.columns else "N/A"
            w_spread = float(winner["spread"][0]) if "spread" in winner.columns else 0.0
            w_volume = float(winner["volume"][0]) if "volume" in winner.columns else 0.0
        else:
            cand_count = 0
            peak_conf = 0.0
            mean_conf = 0.0
            above_060 = above_065 = above_070 = above_075 = 0
            published = 0
            w_underlying = "N/A"
            w_expiry = "N/A"
            w_spread = 0.0
            w_volume = 0.0

        if peak_conf > global_peak:
            global_peak = peak_conf

        # Track peak history for rolling calculations
        peak_history.append((w_start, peak_conf))

        # Rolling peak 30m (6 windows) and 60m (12 windows)
        recent_6 = [p for _, p in peak_history[-6:]]
        recent_12 = [p for _, p in peak_history[-12:]]
        rolling_peak_30m = max(recent_6) if recent_6 else 0.0
        rolling_peak_60m = max(recent_12) if recent_12 else 0.0

        # Time since last new high
        time_since_new_high = 0
        for i in range(len(peak_history) - 1, -1, -1):
            if peak_history[i][1] >= global_peak:
                time_since_new_high = (w_start - peak_history[i][0]) / 60000
                break

        ts_human = datetime.fromtimestamp(w_start / 1000).strftime("%H:%M:%S")

        row = {
            "timestamp": ts_human,
            "candidate_count": cand_count,
            "peak_confidence": round(peak_conf, 4),
            "mean_confidence": round(mean_conf, 4),
            "count_above_060": above_060,
            "count_above_065": above_065,
            "count_above_070": above_070,
            "count_above_075": above_075,
            "published": published,
            "winner_underlying": w_underlying,
            "winner_expiry": w_expiry,
            "winner_spread": round(w_spread, 4),
            "winner_volume": round(w_volume, 2),
            "rolling_peak_30m": round(rolling_peak_30m, 4),
            "rolling_peak_60m": round(rolling_peak_60m, 4),
            "time_since_last_new_high": round(time_since_new_high, 1),
        }
        observation_rows.append(row)

        print(f"[{ts_human}] cands={cand_count:>5}  peak={peak_conf:.4f}  "
              f"mean={mean_conf:.4f}  >0.60={above_060:>4}  >0.65={above_065:>4}  "
              f">0.70={above_070:>4}  >0.75={above_075:>4}  "
              f"roll30={rolling_peak_30m:.4f}  roll60={rolling_peak_60m:.4f}  "
              f"winner={w_underlying}")

    print("-" * 100)

    # Write observation CSV
    os.makedirs("reports", exist_ok=True)
    with open("reports/trade_readiness_o2.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=observation_rows[0].keys())
        writer.writeheader()
        writer.writerows(observation_rows)

    # Final totals
    total_published = sum(r["published"] for r in observation_rows)
    confidence_improvement = global_peak - o1_peak

    if total_published > 0:
        decision = "FIRST_REAL_TRADE"
    elif global_peak >= 0.72:
        decision = "VERY_CLOSE"
    elif confidence_improvement > 0.05:
        decision = "ENERGY_BUILDING"
    elif global_peak < 0.67:
        decision = "FLAT_MARKET"
    else:
        decision = "PIPELINE_HEALTHY"

    print(f"\nOUTPUT:")
    print(f"hours_observed: {session_hours:.2f}")
    print(f"peak_confidence: {global_peak:.4f}")
    print(f"published: {total_published}")
    print(f"decision: {decision}")
    print("STOP")


if __name__ == "__main__":
    main()
