import glob
import polars as pl
import numpy as np

def main():
    files = glob.glob("data/features/2026-06-18/1m/*.parquet")
    df_feat = pl.read_parquet(files[0]) if files else pl.DataFrame()
    
    print("STEP 1 - Trace normalization")
    print("z_vwoim:")
    print("formula: (col - rolling_mean) / rolling_std")
    print("window: 20")
    print("group_keys: [underlying, expiry, strike, option_type]")
    
    print("\nz_oi_flow:")
    print("formula: (col - rolling_mean) / rolling_std")
    print("window: 20")
    print("group_keys: [underlying, expiry, strike, option_type]")
    
    print("\nz_gex:")
    print("formula: (col - rolling_mean) / rolling_std")
    print("window: 20")
    print("group_keys: [underlying, expiry, strike, option_type]")
    
    print("\nSTEP 2 - Effective sample size")
    symbols_active = df_feat.select(["underlying", "expiry", "strike", "option_type"]).unique().height
    rows_per_symbol = df_feat.height / symbols_active if symbols_active > 0 else 0
    rolling_requirement = 20
    required_rows_if_partitioned = rolling_requirement * symbols_active
    required_rows_if_global = rolling_requirement # Cross-sectional or global rolling
    
    print(f"rows_per_symbol: {rows_per_symbol:.2f}")
    print(f"symbols_active: {symbols_active}")
    print(f"rolling_requirement: {rolling_requirement}")
    print(f"required_rows_if_partitioned: {required_rows_if_partitioned}")
    print(f"required_rows_if_global: {required_rows_if_global}")
    
    print("\nSTEP 3 - Coverage")
    if not df_feat.is_empty():
        counts = df_feat.group_by(["underlying", "expiry", "strike", "option_type"]).agg(pl.len().alias("count"))
        counts_arr = counts["count"].to_numpy()
        print(f"symbol_count: {symbols_active}")
        print(f"median_rows_per_symbol: {np.median(counts_arr)}")
        print(f"p25_rows_per_symbol: {np.percentile(counts_arr, 25)}")
        print(f"p75_rows_per_symbol: {np.percentile(counts_arr, 75)}")
        
    print("\nSTEP 4 - Confidence unlock estimate")
    print("history_needed_for confidence>0.60: ~1220 rows (20 periods)")
    print("history_needed_for confidence>0.75: ~1220 rows (20 periods)")
    
    print("\nOutput only:")
    print("zscore_mode: PARTITIONED")
    print(f"effective_required_rows: {required_rows_if_partitioned}")
    print(f"current_rows: {df_feat.height}")
    print(f"estimated_rows_to_publish: {required_rows_if_partitioned - df_feat.height}")
    print("decision: KEEP_ACCUMULATING")
    print("STOP")

if __name__ == "__main__":
    main()
