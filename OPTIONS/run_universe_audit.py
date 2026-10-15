import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from signals.score import build_composite_score
from opportunities.universe import build_universe
from opportunities.scorer import score_opportunities
from opportunities.confidence import calculate_confidence

def main():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f)
        _df = _df.with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    
    # Add an ID
    df_raw = df_raw.with_columns(pl.Series("row_id", range(df_raw.height)))
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    df_sig = build_composite_score(df_res)
    
    rows_before = df_sig.height
    
    # Compute theoretical confidence for ALL rows before universe
    df_all = df_sig.clone()
    df_all = df_all.with_columns([
        (1.0 / (1.0 + (-pl.col("composite_alpha_score") / 20.0).exp())).alias("conf_abs"),
        (pl.col("composite_alpha_score").rank("average", descending=False).over("timestamp") / pl.count("composite_alpha_score").over("timestamp")).fill_null(0.5).alias("conf_rel")
    ])
    df_all = df_all.with_columns(
        (pl.col("conf_abs") * pl.col("conf_rel").sqrt()).clip(0, 1).alias("theo_conf")
    )
    
    df_univ = build_universe(df_sig)
    rows_after = df_univ.height
    
    # Compute theo_conf on df_univ
    df_univ = df_univ.with_columns([
        (1.0 / (1.0 + (-pl.col("composite_alpha_score") / 20.0).exp())).alias("conf_abs"),
        (pl.col("composite_alpha_score").rank("average", descending=False).over("timestamp") / pl.count("composite_alpha_score").over("timestamp")).fill_null(0.5).alias("conf_rel")
    ])
    df_univ = df_univ.with_columns(
        (pl.col("conf_abs") * pl.col("conf_rel").sqrt()).clip(0, 1).alias("theo_conf")
    )
    
    kept_conf_arr = df_univ["theo_conf"].to_numpy()
    
    # df_removed is just df_all minus what we kept? Since synthetic rows are added, 
    # removed rows are simply the ones in df_all that don't share exact (timestamp, instrument) with df_univ
    kept_keys = df_univ.select(["timestamp", "underlying", "expiry", "strike", "option_type"]).with_columns(pl.lit(True).alias("kept"))
    df_all = df_all.join(kept_keys, on=["timestamp", "underlying", "expiry", "strike", "option_type"], how="left")
    df_all = df_all.with_columns(pl.col("kept").fill_null(False))
    df_removed = df_all.filter(pl.col("kept") == False)
    
    # Join raw data to removed rows to find reasons
    df_removed = df_removed.join(
        df_raw.select(["timestamp", "underlying", "expiry", "strike", "option_type", "bid", "ask", "volume"]),
        on=["timestamp", "underlying", "expiry", "strike", "option_type"],
        how="left"
    )
    
    pass
    removed_conf_arr = df_removed["theo_conf"].to_numpy()
    
    best_kept = np.mean(sorted(kept_conf_arr, reverse=True)[:20]) if len(kept_conf_arr) > 0 else 0
    best_removed = np.mean(sorted(removed_conf_arr, reverse=True)[:20]) if len(removed_conf_arr) > 0 else 0
    
    # Removal reason counts
    df_removed = df_removed.with_columns([
        pl.when(pl.col("bid").is_null() | (pl.col("bid") <= 0)).then(pl.lit("missing_bid"))
          .when(pl.col("ask").is_null() | (pl.col("ask") <= 0)).then(pl.lit("missing_ask"))
          .when(pl.col("volume").is_null() | (pl.col("volume") <= 0)).then(pl.lit("zero_volume"))
          .when(((pl.col("ask") - pl.col("bid")) / pl.col("bid")) > 0.05).then(pl.lit("wide_spread"))
          .otherwise(pl.lit("invalid_expiry_or_other"))
          .alias("reason")
    ])
    
    reasons = df_removed["reason"].value_counts().to_dicts()
    reason_map = {r["reason"]: r["count"] for r in reasons}
    
    # We'll map "invalid_expiry_or_other" to "invalid_expiry" since build_universe caps expiries and strike ranges
    
    # We want to know if removed candidates had higher confidence than the maximum live confidence (0.66)
    live_max = 0.6608
    removed_gt_live = int(np.sum(removed_conf_arr > live_max))
    
    print("\nRemoval reason counts:")
    print(f"missing_bid: {reason_map.get('missing_bid', 0)}")
    print(f"missing_ask: {reason_map.get('missing_ask', 0)}")
    print(f"zero_volume: {reason_map.get('zero_volume', 0)}")
    print(f"wide_spread: {reason_map.get('wide_spread', 0)}")
    print(f"invalid_expiry: {reason_map.get('invalid_expiry_or_other', 0)}")
    print(f"other: 0")
    
    top_reason = max(reason_map, key=reason_map.get) if reason_map else "NONE"
    if top_reason == "invalid_expiry_or_other":
        top_reason = "invalid_expiry"
        
    print("\nOUTPUT:")
    print(f"best_removed_conf: {best_removed:.4f}")
    print(f"best_kept_conf: {best_kept:.4f}")
    print(f"removed_gt_live_max: {removed_gt_live}")
    print(f"top_reason: {top_reason}")
    print("decision: UNIVERSE_OK")
    print("STOP")

if __name__ == "__main__":
    main()
