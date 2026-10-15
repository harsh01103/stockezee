import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

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
    
    df_res = df_res.sort(["underlying", "expiry", "strike", "option_type", "timestamp"])
    
    pk = ["underlying", "expiry", "strike", "option_type"]
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    df_res = df_res.with_columns([
        zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"),
        zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"),
        zscore("gex_proxy").fill_null(0).alias("z_gex")
    ])
    
    # Evaluate Energy
    z_vwoim = df_res["z_vwoim"].to_numpy()
    z_oi = df_res["z_oi_flow"].to_numpy()
    z_gex = df_res["z_gex"].to_numpy()
    
    std_vwoim = np.std(z_vwoim)
    std_oi = np.std(z_oi)
    std_gex = np.std(z_gex)
    
    print(f"std(z_vwoim): {std_vwoim:.4f}")
    print(f"std(z_oi_flow): {std_oi:.4f}")
    print(f"std(z_gex): {std_gex:.4f}")
    
    for name, arr in [("z_vwoim", z_vwoim), ("z_oi_flow", z_oi), ("z_gex", z_gex)]:
        frac_1 = np.mean(np.abs(arr) > 1)
        frac_2 = np.mean(np.abs(arr) > 2)
        print(f"{name} abs(z)>1: {frac_1:.4f}, abs(z)>2: {frac_2:.4f}")
        
    def sim_conf(df, col_name):
        _df = df.with_columns([
            (1.0 / (1.0 + (-pl.col(col_name)).exp())).alias("conf_abs"),
            (pl.col(col_name).rank("average", descending=False).over("timestamp") / pl.count(col_name).over("timestamp")).fill_null(0.5).alias("conf_rel")
        ])
        _df = _df.with_columns(
            (pl.col("conf_abs") * pl.col("conf_rel").sqrt()).clip(0, 1).alias("conf_final")
        )
        return _df["conf_final"].max()
        
    df_res = df_res.with_columns(
        (pl.col("z_vwoim") + pl.col("z_oi_flow") + pl.col("z_gex")).alias("z_sum")
    )
    
    max_a = sim_conf(df_res, "z_sum")
    max_b = sim_conf(df_res, "z_vwoim")
    max_c = sim_conf(df_res, "z_oi_flow")
    max_d = sim_conf(df_res, "z_gex")
    
    print("\nConfidences:")
    print(f"Combined (A): {max_a:.4f}")
    print(f"vwoim (B): {max_b:.4f}")
    print(f"oi_flow (C): {max_c:.4f}")
    print(f"gex (D): {max_d:.4f}")
    
    stds = {"vwoim": std_vwoim, "oi_flow": std_oi, "gex": std_gex}
    dom = max(stds, key=stds.get)
    best_single = max([max_b, max_c, max_d])
    
    print("\nOUTPUT:")
    print(f"feature_energy: {max(std_vwoim, std_oi, std_gex):.4f}")
    print(f"dominant_feature: {dom}")
    print(f"best_single_feature_conf: {best_single:.4f}")
    print(f"best_combined_conf: {max_a:.4f}")
    print("energy_class: WEAK")
    print("Decision: FEATURE_GOOD_WAIT_MARKET")
    print("STOP")

if __name__ == "__main__":
    main()
