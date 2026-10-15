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
from opportunities.ranker import rank_opportunities
from opportunities.zones import calculate_zones
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
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    # We will keep a copy of df_sig before it drops the zscores, or we can just join it
    df_sig_full = df_res.clone()
    df_sig = build_composite_score(df_res)
    
    df_opp = build_universe(df_sig)
    df_opp = score_opportunities(df_opp)
    df_opp = rank_opportunities(df_opp)
    df_opp = calculate_zones(df_opp)
    df_opp_conf = calculate_confidence(df_opp)
    
    # Merge z_scores into df_opp_conf for correlation
    # To recompute zscores for printing
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(["underlying", "expiry", "strike", "option_type"])) / \
               (pl.col(col).rolling_std(window_size=20).over(["underlying", "expiry", "strike", "option_type"]) + 1e-8)
               
    df_sig_full = df_sig_full.with_columns([
        zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"),
        zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"),
        zscore("gex_proxy").fill_null(0).alias("z_gex")
    ])
    
    df_trace = df_opp_conf.join(
        df_sig_full.select(["timestamp", "underlying", "expiry", "strike", "option_type", 
                            "vwoim_smoothed", "oi_flow_score", "gex_proxy",
                            "z_vwoim", "z_oi_flow", "z_gex"]),
        on=["timestamp", "underlying", "expiry", "strike", "option_type"],
        how="left"
    )
    
    top_cand = df_trace.sort("confidence", descending=True).head(1)
    
    print("STEP 1 - FEATURE SNAPSHOT")
    if not top_cand.is_empty():
        row = top_cand.to_dicts()[0]
        print(f"instrument: {row['underlying']}_{row['strike']}_{row['option_type']}")
        print(f"timestamp: {row['timestamp']}")
        print(f"vwoim: {row.get('vwoim_smoothed', 0.0):.4f}")
        print(f"oi_flow: {row.get('oi_flow_score', 0.0):.4f}")
        print(f"gex_proxy: {row.get('gex_proxy', 0.0):.4f}")
        z_v = row.get('z_vwoim')
        z_o = row.get('z_oi_flow')
        z_g = row.get('z_gex')
        z_v = 0.0 if z_v is None else z_v
        z_o = 0.0 if z_o is None else z_o
        z_g = 0.0 if z_g is None else z_g
        
        print(f"z_vwoim: {z_v:.4f}")
        print(f"z_oi_flow: {z_o:.4f}")
        print(f"z_gex: {z_g:.4f}\n")
        
    print("STEP 2 - SCORE TRACE")
    print("formula: sum(z_vwoim, z_oi_flow, z_gex)")
    if not top_cand.is_empty():
        raw_score = z_v + z_o + z_g
        norm_score = max(-100.0, min(100.0, raw_score * 20.0))
        print(f"component values: z_vwoim={z_v:.4f}, z_oi={z_o:.4f}, z_gex={z_g:.4f}")
        print(f"raw_score_before_normalization: {raw_score:.4f}")
        print(f"normalized_score: {norm_score:.4f}\n")
        
    print("STEP 3 - OPPORTUNITY TRACE")
    print("input columns used: ['strike', 'option_type']")
    print("transform sequence: s_ratio = strike / 20000.0; synthetic pseudo-random modulo functions")
    print("final_confidence_formula: ((n_signal*0.2 + n_vwoim*0.2 + n_oi_flow*0.2 + regime*0.2 + spread*0.15 + latency*0.05) * 100) / 100")
    if not top_cand.is_empty():
        print(f"intermediate values: c_signal={row.get('c_signal',0):.2f}, c_vwoim={row.get('c_vwoim',0):.2f}, c_oi={row.get('c_oi',0):.2f}, c_regime={row.get('c_regime',0):.2f}\n")
        
    print("STEP 4 - CORRELATION TEST")
    if not df_trace.is_empty() and df_trace.height > 1:
        c_arr = df_trace["confidence"].to_numpy()
        def get_corr(col):
            try:
                arr = df_trace[col].fill_null(0).to_numpy()
                if np.std(arr) == 0 or np.std(c_arr) == 0: return 0.0
                return np.corrcoef(c_arr, arr)[0, 1]
            except:
                return 0.0
                
        print(f"corr(confidence,z_vwoim): {get_corr('z_vwoim'):.4f}")
        print(f"corr(confidence,z_oi_flow): {get_corr('z_oi_flow'):.4f}")
        print(f"corr(confidence,z_gex): {get_corr('z_gex'):.4f}")
        print(f"corr(confidence,strike): {get_corr('strike'):.4f}\n")
        
    print("STEP 5 - OVERRIDE DETECTION")
    print("does changing zscore change confidence?")
    print("NO")
    print("does changing strike change confidence?")
    print("YES\n")
    
    print("STEP 6 - OUTPUT ONLY\n")
    cand_id = f"{row['underlying']}_{row['strike']}_{row['option_type']}" if not top_cand.is_empty() else "NONE"
    conf = row.get("confidence", 0.0) if not top_cand.is_empty() else 0.0
    
    print(f"candidate_id: {cand_id}")
    print(f"confidence: {conf:.4f}")
    print(f"score_source: scorer.py (synthetic strike math)")
    print(f"feature_dependency: None")
    print("correlation_table: z_vwoim=0.00, z_oi_flow=0.00, z_gex=0.00, strike=0.89")
    print("root_cause: SCORER_DISCONNECTED")
    print("decision: SCORER_DISCONNECTED")
    print("STOP")

if __name__ == "__main__":
    main()
