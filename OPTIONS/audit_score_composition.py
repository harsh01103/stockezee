import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
import polars as pl
import numpy as np

from opportunities.universe import build_universe
from opportunities.scorer import score_opportunities
from opportunities.ranker import rank_opportunities

def audit_components(df: pl.DataFrame):
    """Step 1 & 2: Component Contribution & Concentration"""
    comps = ["c_signal", "c_vwoim", "c_oi", "c_regime", "c_spread", "c_latency"]
    
    if df.is_empty() or not all(c in df.columns for c in comps):
        return False, {"hhi": 1.0, "effective_components": 1.0}
        
    df = df.with_columns(
        (pl.col("c_signal") + pl.col("c_vwoim") + pl.col("c_oi") + 
         pl.col("c_regime") + pl.col("c_spread") + pl.col("c_latency") + 1e-6).alias("comp_total")
    )
    
    for c in comps:
        df = df.with_columns((pl.col(c) / pl.col("comp_total")).alias(f"pct_{c}"))
        
    Path("reports").mkdir(exist_ok=True)
    with open("reports/component_share.csv", "w") as f:
        f.write("component,mean,median,p90\n")
        means = []
        for c in comps:
            s = df[f"pct_{c}"]
            c_mean = float(s.mean())
            c_med = float(s.median())
            c_p90 = float(s.quantile(0.9))
            f.write(f"{c},{c_mean},{c_med},{c_p90}\n")
            means.append(c_mean)
            
    # HHI
    means = np.array(means)
    hhi = np.sum(means ** 2)
    
    # Entropy
    entropy = -np.sum(means * np.log(means + 1e-9))
    
    # Effective Components
    effective_components = np.exp(entropy)
    
    passed = (hhi <= 0.35) and (effective_components >= 3.0)
    
    return passed, {
        "hhi": float(hhi),
        "entropy": float(entropy),
        "effective_components": float(effective_components)
    }

def perform_ablation(df: pl.DataFrame):
    """Step 3: Ablation"""
    comps = ["c_signal", "c_vwoim", "c_oi", "c_regime", "c_spread", "c_latency"]
    
    if df.is_empty():
        return False, 0.0
        
    # Base rank
    base_ranked = rank_opportunities(df)
    base_top5 = base_ranked.filter(pl.col("rank") <= 5)
    
    max_delta_rank_pct = 0.0
    
    # Re-calculate rank without one component
    for c in comps:
        # We need to simulate 'scorer.py' dropping a component. 
        # Since scorer exposes 'c_signal', we can just subtract it from the raw sum, 
        # but 'opportunity_score' was scaled exactly 0-100 after sum.
        # Let's approximate ablation by just ranking without that component.
        
        ablation_score_col = "ablation_score"
        
        ablate_expr = pl.col("opportunity_score_raw") * 100.0 - pl.col(c) if "opportunity_score_raw" in df.columns else pl.col("opportunity_score") - pl.col(c)
        df_ablated = df.with_columns(ablate_expr.alias("opportunity_score"))
        
        ablated_ranked = rank_opportunities(df_ablated)
        abl_top5 = ablated_ranked.filter(pl.col("rank") <= 5)
        
        # Measure difference in sets
        if base_top5.height > 0:
            # We assume 'instrument_key' identifies them
            base_set = set(base_top5["instrument_key"].to_list())
            abl_set = set(abl_top5["instrument_key"].to_list())
            
            diff = len(base_set - abl_set)
            delta_rank_pct = diff / len(base_set)
            max_delta_rank_pct = max(max_delta_rank_pct, delta_rank_pct)
            
    passed = max_delta_rank_pct <= 0.40
    return passed, float(max_delta_rank_pct)

def audit_score_stability(df: pl.DataFrame):
    """Step 4: Score Stability (Bootstrap)"""
    if df.is_empty():
        return False, 0.0
        
    # We will sample candidates with replacement for a timestamp, rank them, and check if top5 overlaps
    base_ranked = rank_opportunities(df)
    base_top5 = base_ranked.filter(pl.col("rank") <= 5)
    if base_top5.height == 0:
        return False, 0.0
        
    base_set = set(base_top5["instrument_key"].to_list())
    
    overlaps = []
    np.random.seed(123)
    
    for _ in range(100):
        # sample df
        indices = np.random.choice(df.height, size=df.height, replace=True)
        # Using polars indices:
        df_boot = df[indices.tolist()]
        
        # Rank the bootstrap sample
        # (It will group by timestamp and rank)
        boot_ranked = rank_opportunities(df_boot)
        boot_top5 = boot_ranked.filter(pl.col("rank") <= 5)
        
        boot_set = set(boot_top5["instrument_key"].to_list())
        
        overlap = len(base_set.intersection(boot_set)) / len(base_set)
        overlaps.append(overlap)
        
    persistence = np.mean(overlaps)
    passed = persistence >= 0.60
    
    return passed, float(persistence)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    date_str = args.date
    base_dir = Path(f"data/signals/{date_str}")
    
    if not base_dir.exists():
        print(f"No signals data found for {date_str}")
        sys.exit(1)
        
    interval_dir = base_dir / "1m"
    if not interval_dir.exists():
        print("No 1m data found")
        sys.exit(1)
        
    files = list(interval_dir.glob("*.parquet"))
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    
    print(f"Loaded {df.height} signal rows.")
    
    # Generate scores
    df_uni = build_universe(df)
    df_scored = score_opportunities(df_uni)
    
    pass12, comp_metrics = audit_components(df_scored)
    pass3, max_delta_rank = perform_ablation(df_scored)
    pass4, rank_persistence = audit_score_stability(df_scored)
    
    passed = pass12 and pass3 and pass4
    grade = "PASS" if passed else "FAIL"
    
    report = {
        "grade": grade,
        "component_balance": bool(pass12),
        "hhi": comp_metrics["hhi"],
        "effective_components": comp_metrics["effective_components"],
        "rank_stability": rank_persistence,
        "max_ablation_impact": max_delta_rank
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase3a_balance.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Component Balance: {report['component_balance']}")
    print(f"HHI: {report['hhi']:.4f}")
    print(f"Effective Components: {report['effective_components']:.2f}")
    print(f"Rank Stability: {report['rank_stability']:.2f}")
    print(f"Max Ablation Impact: {report['max_ablation_impact']:.2f}")
    
    if passed:
        print("\nPASS")
        print("PHASE 3A.3.1 COMPLETE")
    else:
        print("\nFAIL")
        if not pass12: print("FAILED: HHI > 0.35 or effective_components < 3")
        if not pass3: print("FAILED: single removal >40%")
        if not pass4: print("FAILED: top5 persistence <60%")

if __name__ == "__main__":
    main()
