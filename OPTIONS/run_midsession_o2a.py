"""
PHASE O2A — MIDSESSION ENERGY TRACK
Observes pipeline every 10 minutes for 60 minutes using only fresh captured data.
"""
import glob
import os
import time
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
    def zscore(col):
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


def run_snapshot(date_str: str):
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    if not raw_files:
        return None, 0

    dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    total_rows = df_raw.height

    res = process_features(df_raw, date_str, dry_run=False)
    df_res = compute_gex_proxy(compute_regime_features(compute_vwoim(compute_oi_flow(res["df_features"]))))
    df_res = df_res.sort("timestamp")
    df_sig = build_composite(df_res)

    all_cands = []
    for ts in sorted(df_sig["timestamp"].unique().to_list()):
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
        if not df_opp.is_empty() and "confidence" in df_opp.columns:
            all_cands.append(df_opp)

    df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()
    return df_out, total_rows


def main():
    date_str = "2026-06-19"
    baseline_peak = 0.6879  # From O1C at 10:48
    intervals = 7  # 0, 10, 20, 30, 40, 50, 60 minutes
    interval_sec = 600  # 10 minutes
    observations = []
    global_peak = 0.0
    start_time = time.time()

    print(f"PHASE O2A — MIDSESSION ENERGY TRACK")
    print(f"Start: {datetime.now().strftime('%H:%M:%S')} IST")
    print(f"Baseline peak: {baseline_peak:.4f}")
    print("-" * 120)

    for i in range(intervals):
        if i > 0:
            print(f"\n  ... waiting 10 minutes (next snapshot at +{i*10}m) ...")
            time.sleep(interval_sec)

        ts_human = datetime.now().strftime("%H:%M:%S")
        df_out, total_rows = run_snapshot(date_str)
        parquet_count = len(glob.glob(f"data/raw/{date_str}/*.parquet"))

        if df_out is None or df_out.is_empty():
            row = {
                "timestamp": ts_human, "rows_captured": total_rows,
                "candidate_count": 0, "peak_confidence": 0.0, "mean_confidence": 0.0,
                "count_above_060": 0, "count_above_065": 0,
                "count_above_070": 0, "count_above_075": 0,
                "published": 0, "winner_confidence": 0.0,
                "winner_volume": 0.0, "winner_spread": 0.0,
                "rolling_peak": 0.0, "delta_vs_10_48": 0.0,
            }
        else:
            peak_conf = float(df_out["confidence"].max())
            mean_conf = float(df_out["confidence"].mean())
            above_060 = df_out.filter(pl.col("confidence") > 0.60).height
            above_065 = df_out.filter(pl.col("confidence") > 0.65).height
            above_070 = df_out.filter(pl.col("confidence") > 0.70).height
            above_075 = df_out.filter(pl.col("confidence") > 0.75).height
            published = above_075

            winner = df_out.sort("confidence", descending=True).head(1)
            w_conf = float(winner["confidence"][0])
            w_vol = float(winner["volume"][0]) if "volume" in winner.columns else 0.0
            w_spread = float(winner["spread"][0]) if "spread" in winner.columns else 0.0

            if peak_conf > global_peak:
                global_peak = peak_conf

            row = {
                "timestamp": ts_human, "rows_captured": total_rows,
                "candidate_count": df_out.height,
                "peak_confidence": round(peak_conf, 4),
                "mean_confidence": round(mean_conf, 4),
                "count_above_060": above_060,
                "count_above_065": above_065,
                "count_above_070": above_070,
                "count_above_075": above_075,
                "published": published,
                "winner_confidence": round(w_conf, 4),
                "winner_volume": round(w_vol, 2),
                "winner_spread": round(w_spread, 4),
                "rolling_peak": round(global_peak, 4),
                "delta_vs_10_48": round(peak_conf - baseline_peak, 4),
            }

        observations.append(row)
        print(f"[{ts_human}] rows={row['rows_captured']:>6}  cands={row['candidate_count']:>5}  "
              f"peak={row['peak_confidence']:.4f}  mean={row['mean_confidence']:.4f}  "
              f">0.60={row['count_above_060']:>4}  >0.65={row['count_above_065']:>4}  "
              f">0.70={row['count_above_070']:>4}  >0.75={row['count_above_075']:>4}  "
              f"delta={row['delta_vs_10_48']:+.4f}  winner={row['winner_confidence']:.4f}")

    print("-" * 120)

    # Write CSV
    os.makedirs("reports", exist_ok=True)
    with open("reports/midsession_o2a.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=observations[0].keys())
        writer.writeheader()
        writer.writerows(observations)

    elapsed_hours = (time.time() - start_time) / 3600
    total_published = sum(r["published"] for r in observations)
    final_delta = observations[-1]["delta_vs_10_48"] if observations else 0.0

    if total_published > 0:
        decision = "FIRST_REAL_TRADE"
    elif global_peak >= 0.72:
        decision = "VERY_CLOSE"
    elif final_delta >= 0.03:
        decision = "ENERGY_EXPANDING"
    elif final_delta < 0:
        decision = "MORNING_FADE"
    else:
        decision = "STABLE"

    print(f"\nOUTPUT:")
    print(f"hours_observed: {elapsed_hours:.2f}")
    print(f"peak_confidence: {global_peak:.4f}")
    print(f"delta: {final_delta:+.4f}")
    print(f"published: {total_published}")
    print(f"decision: {decision}")
    print("STOP")


if __name__ == "__main__":
    main()
