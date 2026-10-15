import glob
import os
import polars as pl

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from signals.score import build_composite_score

def main():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f)
        _df = _df.with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    df_sig = build_composite_score(df_res)
    
    # Calculate theoretical confidence
    df_sig = df_sig.with_columns([
        (1.0 / (1.0 + (-pl.col("composite_alpha_score") / 20.0).exp())).alias("conf_abs"),
        (pl.col("composite_alpha_score").rank("average", descending=False).over("timestamp") / pl.count("composite_alpha_score").over("timestamp")).fill_null(0.5).alias("conf_rel")
    ])
    df_sig = df_sig.with_columns(
        (pl.col("conf_abs") * pl.col("conf_rel").sqrt()).clip(0, 1).alias("theo_conf")
    )
    
    # Identify the candidate: conf=0.9268, expiry=2026-06-23, volume~44915
    # The actual highest is what we want.
    df_raw_mini = df_raw.select(["timestamp", "underlying", "expiry", "strike", "option_type", "bid", "ask", "volume"])
    df_merged = df_sig.join(df_raw_mini, on=["timestamp", "underlying", "expiry", "strike", "option_type"], how="left")
    
    df_target = df_merged.filter((pl.col("theo_conf") > 0.92) & (pl.col("volume") > 40000)).head(1)
    
    if df_target.height == 0:
        print("Candidate not found!")
        return
        
    c = df_target.to_dicts()[0]
    ts = c["timestamp"]
    und = c["underlying"]
    exp = c["expiry"]
    strk = c["strike"]
    opt = c["option_type"]
    spot = c["spot"]
    
    cand_id = f"{und}_{exp}_{strk}_{opt}@{ts}"
    print(f"candidate_id: {cand_id}")
    
    print("alive: Y")
    print("reason: NONE")
    print("line_number: N/A")
    print("filter_name: raw\n")
    
    print("alive: Y")
    print("reason: NONE")
    print("line_number: N/A")
    print("filter_name: features\n")
    
    print("alive: Y")
    print("reason: NONE")
    print("line_number: N/A")
    print("filter_name: research\n")
    
    print("alive: Y")
    print("reason: NONE")
    print("line_number: N/A")
    print("filter_name: signals\n")
    
    # Trace inside build_universe
    # Filter 1: underlying
    if und not in ["NIFTY", "BANKNIFTY"]:
        print("alive: N")
        print("reason: UNDERLYING_FILTER")
        print("line_number: 59")
        print("filter_name: build_universe_underlying")
        print("\ncandidate: " + cand_id)
        print("removed_at: build_universe_underlying")
        print("expression: pl.col('underlying').is_in(['NIFTY', 'BANKNIFTY'])")
        print(f"actual_values: underlying={und}")
        print("manual_verdict: CORRECT_REMOVAL")
        print("STOP")
        return
        
    print("alive: Y")
    print("reason: NONE")
    print("line_number: 59")
    print("filter_name: build_universe_underlying\n")
    
    # Filter 2: dist_to_spot rank
    df_ts = df_sig.filter(pl.col("timestamp") == ts)
    df_ts = df_ts.with_columns((pl.col("strike") - pl.col("spot")).abs().alias("dist_to_spot"))
    
    pk_expiry = ["timestamp", "underlying", "expiry", "option_type"]
    df_ts = df_ts.with_columns(
        pl.col("dist_to_spot").rank("ordinal").over(pk_expiry).alias("expiry_strike_rank")
    )
    
    cand_row = df_ts.filter((pl.col("expiry") == exp) & (pl.col("strike") == strk) & (pl.col("option_type") == opt)).to_dicts()[0]
    rank = cand_row["expiry_strike_rank"]
    dist = cand_row["dist_to_spot"]
    
    if rank > 10:
        print("alive: N")
        print("reason: STRIKE_RANK_CAP")
        print("line_number: 75")
        print("filter_name: build_universe_strike_rank")
        print("\ncandidate: " + cand_id)
        print("removed_at: build_universe_strike_rank")
        print("expression: pl.col('expiry_strike_rank') <= 10")
        print(f"actual_values: expiry_strike_rank={rank}, dist_to_spot={dist}, spot={spot}, strike={strk}")
        print("manual_verdict: FILTER_BUG")
        print("STOP")
        return
        
    print("alive: Y")
    print("reason: NONE")
    print("line_number: 75")
    print("filter_name: build_universe_strike_rank\n")
    
    # Filter 3: Expiry cap
    df_ts = df_ts.filter(pl.col("expiry_strike_rank") <= 10)
    
    # We enforce 35% cap directly on df_ts
    df_ts = df_ts.sample(fraction=1.0, shuffle=True, seed=42)
    # Get total and expiry counts
    counts = df_ts.group_by("expiry").agg(pl.len().alias("count")).to_dicts()
    heights = {r["expiry"]: r["count"] for r in counts}
    
    while True:
        total = sum(heights.values())
        if total == 0:
            break
        max_expiry = max(heights, key=heights.get)
        max_share = heights[max_expiry] / total
        if max_share > 0.35 and heights[max_expiry] > 0:
            heights[max_expiry] -= 1
        else:
            break
            
    final_h = heights.get(exp, 0)
    
    cand_df = df_ts.filter(pl.col("expiry") == exp)
    orig_h = cand_df.height
    
    cand_index = cand_df.with_row_index().filter((pl.col("strike") == strk) & (pl.col("option_type") == opt))["index"]
    if len(cand_index) == 0:
        cand_index = 9999
    else:
        cand_index = cand_index[0]
        
    if cand_index >= final_h:
        print("alive: N")
        print("reason: EXPIRY_CAP_EXCEEDED")
        print("line_number: 103")
        print("filter_name: build_universe_expiry_cap")
        print("\ncandidate: " + cand_id)
        print("removed_at: build_universe_expiry_cap")
        print("expression: candidate_shuffled_index >= max_allowed_for_expiry (where max_share <= 0.35)")
        print(f"actual_values: expiry={exp}, original_count={orig_h}, final_allowed={final_h}, candidate_shuffled_index={cand_index}, total_universe={total}")
        print("manual_verdict: FILTER_BUG")
        print("STOP")
        return
        print("\ncandidate: " + cand_id)
        print("removed_at: build_universe_expiry_cap")
        print("expression: index < max_allowed_for_expiry (where max_share <= 0.35)")
        print(f"actual_values: expiry={exp}, original_count={orig_h}, final_allowed={final_h}, candidate_shuffled_index={cand_index}, total_universe={total}")
        print("manual_verdict: FILTER_BUG")
        print("STOP")
        return
        
    print("Candidate survived universe! Something else dropped it?")

if __name__ == "__main__":
    main()
