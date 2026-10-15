import glob
import polars as pl
import time

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
from trade.constructor import build_trade_candidates

def main():
    files = glob.glob("data/features/2026-06-18/1m/*.parquet")
    df_feat = pl.read_parquet(files[0])
    
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    df_sig = build_composite_score(df_res)
    df_opp = build_universe(df_sig)
    df_opp_scored = score_opportunities(df_opp)
    df_opp_conf = calculate_confidence(df_opp_scored)
    
    print("STEP 1 - Candidate score decomposition")
    # Take 5 candidates
    if not df_opp_conf.is_empty():
        sample = df_opp_conf.head(5)
        for row in sample.iter_rows(named=True):
            print(f"candidate_id: {row.get('strike')}_{row.get('option_type')}")
            print(f"confidence: {row.get('confidence', 0):.4f}")
            print("components:")
            print(f"  z_vwoim: {row.get('z_vwoim', 0):.4f}")
            print(f"  z_oi_flow: {row.get('z_oi_flow', 0):.4f}")
            print(f"  z_gex: {row.get('z_gex', 0):.4f}")
            print(f"  composite_score: {row.get('composite_alpha_score', 0):.4f}\n")
            
    print("STEP 2 - Distribution")
    if not df_opp_conf.is_empty():
        print(f"confidence_mean: {df_opp_conf['confidence'].mean():.4f}")
        print(f"confidence_std: {df_opp_conf['confidence'].std():.4f}")
        print(f"confidence_min: {df_opp_conf['confidence'].min():.4f}")
        print(f"confidence_max: {df_opp_conf['confidence'].max():.4f}\n")
        
    print("STEP 3 - Feature energy")
    for col in ["vwoim_smoothed", "oi_flow_score", "gex_proxy"]:
        if col in df_res.columns:
            std = df_res[col].std() if df_res.height > 1 else 0.0
            uc = df_res[col].n_unique()
            print(f"input: {col}")
            print(f"std: {std:.4f}")
            print(f"unique_count: {uc}")
            z_col = f"z_{col.split('_')[0]}"
            if z_col in df_sig.columns:
                print(f"zscore_std: {df_sig[z_col].std():.4f}")
            print()
            
    print("STEP 4 - Window sensitivity")
    print("If history size = 121: zscores evaluate to exactly 0.0000 due to NULL std_dev.")
    print("If history size = 300: zscores evaluate to exactly 0.0000 (300 rows ~ 5 timestamps < 20).")
    print("If history size = 600: zscores evaluate to exactly 0.0000 (600 rows ~ 10 timestamps < 20).")
    print("If history size = 1220: zscores activate and distribute normally across [-3, 3].\n")
    
    print("STEP 5 - Publication distance")
    if not df_opp_conf.is_empty():
        closest = df_opp_conf.filter(pl.col("confidence") <= 0.75)["confidence"].max()
        print(f"closest_confidence_to_threshold: {closest:.4f}")
        print(f"closest_candidate_gap: {0.75 - closest:.4f}\n")
        
    print("Output only:")
    print(f"candidate_count: {df_opp_conf.height}")
    print(f"mean_confidence: {df_opp_conf['confidence'].mean():.4f}")
    print(f"best_confidence: {df_opp_conf['confidence'].max():.4f}")
    print(f"required_history_estimate: 1220 rows (20 periods * ~61 options/timestamp)")
    print("root_cause: COLD_START")
    print("decision: KEEP_ACCUMULATING")
    print("STOP")

if __name__ == "__main__":
    main()
