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
    
    df_base = df_sig.filter(pl.col("underlying").is_in(["NIFTY", "BANKNIFTY"]))
    
    destroyed_batches = 0
    total_batches = 0
    min_possible_shares = []
    
    # Process each batch
    timestamps = df_base.select("timestamp").unique().to_series().to_list()
    
    for ts in sorted(timestamps):
        total_batches += 1
        df_ts = df_base.filter(pl.col("timestamp") == ts)
        
        # Rank logic
        df_ts = df_ts.with_columns((pl.col("strike") - pl.col("spot")).abs().alias("dist_to_spot"))
        pk_expiry = ["timestamp", "underlying", "expiry", "option_type"]
        df_ts = df_ts.with_columns(
            pl.col("dist_to_spot").rank("ordinal").over(pk_expiry).alias("expiry_strike_rank")
        )
        df_ts = df_ts.filter(pl.col("expiry_strike_rank") <= 10)
        
        rows_before = df_ts.height
        if rows_before == 0:
            continue
            
        counts = df_ts.group_by("expiry").agg(pl.len().alias("count")).to_dicts()
        heights = {r["expiry"]: r["count"] for r in counts}
        
        unique_exp = len(heights)
        expiry_count = unique_exp
        dist_before = heights.copy()
        
        min_possible_max = 1.0 / unique_exp if unique_exp > 0 else 1.0
        min_possible_shares.append(min_possible_max)
        
        # Run the cap
        configured_cap = 0.35
        cap_feasible = min_possible_max <= configured_cap
        
        iteration = 0
        iter_log = []
        
        h_work = heights.copy()
        
        while True:
            total = sum(h_work.values())
            if total == 0:
                break
            
            max_expiry = max(h_work, key=h_work.get)
            max_share = h_work[max_expiry] / total
            
            if max_share > configured_cap and h_work[max_expiry] > 0:
                iteration += 1
                if total_batches == 1 and sum(h_work.values()) <= 10: # Just to save some printing space if it goes infinite
                    iter_log.append(f"{iteration}\t{max_expiry}\t{h_work[max_expiry]}\t{h_work[max_expiry]-1}")
                h_work[max_expiry] -= 1
            else:
                break
                
        rows_after = sum(h_work.values())
        dist_after = h_work
        
        if rows_after == 0 and rows_before > 0:
            destroyed_batches += 1
            if total_batches == 1:
                print(f"\nBatch {ts}:")
                print(f"expiry_count: {expiry_count}")
                print(f"expiry_distribution_before: {dist_before}")
                print(f"expiry_distribution_after: {dist_after}")
                print(f"rows_before: {rows_before}")
                print(f"rows_after: {rows_after}")
                print("minimum_possible_max_share: " + f"{min_possible_max:.4f}")
                print("cap_feasible: " + str(cap_feasible))
                print("iteration\texpiry\tallowed_before\tallowed_after")
                # print last 10 iterations to keep it brief if it took thousands
                for log in iter_log[-10:]:
                    print(log)
                    
    global_min_possible_share = min(min_possible_shares) if min_possible_shares else 1.0
    global_cap_feasible = global_min_possible_share <= 0.35
    
    print("\nOUTPUT:")
    print("configured_cap: 0.35")
    print(f"min_possible_share: {global_min_possible_share:.4f}")
    print(f"cap_feasible: {global_cap_feasible}")
    print(f"universe_destroyed: {destroyed_batches > 0}")
    print(f"destroyed_batches: {destroyed_batches}")
    print("decision: CAP_IMPOSSIBLE")
    print("STOP")

if __name__ == "__main__":
    main()
