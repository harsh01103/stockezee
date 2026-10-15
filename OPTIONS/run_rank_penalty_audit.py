import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

from opportunities.scorer import score_opportunities
from opportunities.universe import build_universe
from opportunities.ranker import rank_opportunities
from opportunities.confidence import calculate_confidence

def build_composite_shadow(df: pl.DataFrame, pk: list) -> pl.DataFrame:
    if df.is_empty():
        return df
        
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
        
    sum_expr = pl.sum_horizontal(features)
    df = df.with_columns(sum_expr.alias("raw_score"))
    
    df = df.with_columns(
        (pl.col("raw_score") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    
    return df

def run_pipeline(df_res: pl.DataFrame, pk: list) -> pl.DataFrame:
    df_sig = build_composite_shadow(df_res, pk)
    
    timestamps = df_sig.select("timestamp").unique().to_series().to_list()
    timestamps = sorted(timestamps)
    
    all_candidates = []
    
    for ts in timestamps:
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        
        # Universe
        df_univ = build_universe(df_ts)
        
        # Scorer
        df_opp = score_opportunities(df_univ)
        
        # We need to trace intermediate values
        if "composite_alpha_score" in df_opp.columns:
            df_opp = df_opp.with_columns([
                (1.0 / (1.0 + (-pl.col("composite_alpha_score") / 20.0).exp())).alias("raw_conf")
            ])
            
        # Ranker
        df_opp = rank_opportunities(df_opp)
        
        # Confidence
        df_opp = calculate_confidence(df_opp)
        
        if "confidence" in df_opp.columns:
            df_opp = df_opp.with_columns(pl.col("confidence").alias("final_conf"))
            
        all_candidates.append(df_opp)
        
    if all_candidates:
        return pl.concat(all_candidates, how="vertical_relaxed")
    return pl.DataFrame()

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
    
    df_res = df_res.sort("timestamp")
    
    pk_B = ["underlying", "expiry"]
    
    df_B = run_pipeline(df_res, pk_B)
    
    if df_B.height == 0:
        print("Empty results.")
        return
        
    # Get top 500 candidates before rank (using raw_conf)
    df_top_raw = df_B.sort("raw_conf", descending=True).head(500)
    
    # Clustering
    clusters = df_top_raw.group_by(["underlying", "expiry"]).agg([
        pl.len().alias("candidate_count_per_cluster"),
        pl.col("raw_conf").max().alias("best_raw"),
        pl.col("final_conf").max().alias("best_final"),
        (pl.col("raw_conf") > 0.75).sum().alias("published_if_no_rank"),
        (pl.col("final_conf") > 0.75).sum().alias("published_with_rank"),
        (pl.col("raw_conf").max() - pl.col("final_conf").max()).alias("top_conf_gap"),
        (pl.col("raw_conf") - pl.col("final_conf")).median().alias("median_conf_gap"),
        pl.col("strike").n_unique().alias("strike_dispersion")
    ])
    
    # top2 conf distance
    # we can find it by sorting within group and taking diff of top 2
    def top2_dist(s):
        s_sorted = sorted(s, reverse=True)
        if len(s_sorted) >= 2:
            return s_sorted[0] - s_sorted[1]
        return 0.0
        
    # Since we can't easily do custom python functions in agg directly without apply, let's just do it sequentially or use top_k
    df_top_2 = df_top_raw.sort(["underlying", "expiry", "raw_conf"], descending=[False, False, True])
    # get 1st and 2nd
    first = df_top_2.group_by(["underlying", "expiry"]).agg(pl.col("raw_conf").first().alias("first"))
    last = df_top_2.group_by(["underlying", "expiry"]).agg(pl.col("raw_conf").slice(1, 1).first().alias("second"))
    
    clusters = clusters.join(first, on=["underlying", "expiry"], how="left")
    clusters = clusters.join(last, on=["underlying", "expiry"], how="left")
    clusters = clusters.with_columns(
        (pl.col("first") - pl.col("second").fill_null(pl.col("first"))).alias("top2_conf_distance")
    )
    
    clusters_count = clusters.height
    publishable_without_rank = clusters["published_if_no_rank"].sum()
    publishable_with_rank = clusters["published_with_rank"].sum()
    
    # Removed candidates: publishable_without_rank - publishable_with_rank
    removed_total = publishable_without_rank - publishable_with_rank
    
    # Are the removed ones in independent clusters?
    clusters_losing_pub = clusters.filter((pl.col("published_if_no_rank") > 0) & (pl.col("best_final") <= 0.75))
    indep_clusters_lost = clusters_losing_pub.height
    
    # removed_unique_pct is percentage of removed candidates that are NOT in the same cluster
    # i.e. if a cluster had 5 publishable and now has 1, 4 duplicates were removed. 
    # But if a cluster had 1 publishable and now has 0, 1 unique was removed.
    # We will count "unique lost" as the number of independent clusters that completely lost their publication.
    removed_unique_pct = (indep_clusters_lost / removed_total * 100.0) if removed_total > 0 else 0.0
    
    mean_top2_dist = clusters["top2_conf_distance"].mean()
    
    decision = ""
    # IF most removed candidates belong to same cluster AND top2_conf_distance < 0.05
    if removed_unique_pct < 50.0 and mean_top2_dist < 0.05:
        decision = "RANK_IS_PROTECTIVE"
    elif indep_clusters_lost > 1:
        decision = "RANK_TOO_AGGRESSIVE"
    else:
        decision = "KEEP_RANK"
        
    print("\nOUTPUT:")
    print(f"clusters: {clusters_count}")
    print(f"publishable_without_rank: {publishable_without_rank}")
    print(f"publishable_with_rank: {publishable_with_rank}")
    print(f"removed_unique_pct: {removed_unique_pct:.2f}%")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
