import argparse
import sys
from datetime import datetime
from pathlib import Path
import polars as pl
import json

from opportunities.universe import build_universe
from opportunities.scorer import score_opportunities
from opportunities.ranker import rank_opportunities

def audit_score_distribution(df: pl.DataFrame):
    """Step 1: Score Distribution"""
    if df.is_empty() or "opportunity_score" not in df.columns:
        return False, 0.0, 0.0
        
    s = df["opportunity_score"].drop_nulls()
    mean_val = s.mean()
    median_val = s.median()
    std_val = s.std()
    p10 = s.quantile(0.1)
    p90 = s.quantile(0.9)
    
    passed = std_val >= 5.0
    return passed, mean_val, std_val

def audit_components(df: pl.DataFrame):
    """Step 2: Component Audit"""
    comps = ["c_signal", "c_vwoim", "c_oi", "c_regime", "c_spread", "c_latency"]
    if df.is_empty() or not all(c in df.columns for c in comps):
        return False, 1.0
        
    # Calculate the average contribution of each component
    total_score = df["opportunity_score"].mean() + 1e-6
    max_ratio = 0.0
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/component_breakdown.csv", "w") as f:
        f.write("component,mean_value,ratio\n")
        for c in comps:
            c_mean = df[c].mean()
            ratio = c_mean / total_score
            max_ratio = max(max_ratio, ratio)
            f.write(f"{c},{c_mean},{ratio}\n")
            
    passed = max_ratio <= 0.70
    return passed, float(max_ratio)

def audit_cross_section(df: pl.DataFrame):
    """Step 3: Cross Section"""
    if df.is_empty():
        return False
        
    # Unique scores per timestamp
    agg = df.group_by("timestamp").agg(pl.col("opportunity_score").n_unique().alias("u_scores"))
    min_unique = agg["u_scores"].min()
    
    passed = min_unique >= 10
    return passed

def audit_score_sanity(df: pl.DataFrame):
    """Step 4: Score Sanity"""
    if df.is_empty():
        return False
        
    s = df["opportunity_score"]
    negative_count = s.filter(s < 0).len()
    nan_count = s.null_count()
    
    # constant ratio
    most_common_count = s.value_counts()["count"].max()
    constant_ratio = most_common_count / df.height
    
    passed = negative_count == 0 and nan_count == 0 and constant_ratio <= 0.05
    return passed

def audit_top_diversity(df: pl.DataFrame):
    """Step 5: Top Candidate Diversity"""
    if df.is_empty():
        return False
        
    # Get top 5 per timestamp
    df_top = rank_opportunities(df)
    
    # Measure strike diversity, expiry diversity, CE/PE ratio
    # If same strike dominates > 80% across all top 5
    strike_counts = df_top["strike"].value_counts()
    max_strike_count = strike_counts["count"].max()
    strike_dominance = max_strike_count / df_top.height
    
    passed = strike_dominance <= 0.80
    return passed, float(strike_dominance)

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
    
    # Rebuild Universe and Score
    df_uni = build_universe(df)
    df_scored = score_opportunities(df_uni)
    
    pass1, avg_score, score_std = audit_score_distribution(df_scored)
    pass2, max_comp_ratio = audit_components(df_scored)
    pass3 = audit_cross_section(df_scored)
    pass4 = audit_score_sanity(df_scored)
    pass5, strike_dominance = audit_top_diversity(df_scored)
    
    passed = pass1 and pass2 and pass3 and pass4 and pass5
    grade = "PASS" if passed else "FAIL"
    
    report = {
        "grade": grade,
        "avg_score": float(avg_score),
        "score_std": float(score_std),
        "candidate_diversity": float(1.0 - strike_dominance),
        "component_balance": float(max_comp_ratio)
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase3a_score.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Avg Score: {report['avg_score']:.2f}")
    print(f"Score Std: {report['score_std']:.2f}")
    print(f"Candidate Diversity: {report['candidate_diversity']:.2f}")
    print(f"Component Balance: {report['component_balance']:.2f}")
    
    if passed:
        print("\nPASS")
        print("PHASE 3A.3 COMPLETE")
    else:
        print("\nFAIL")
        if not pass1: print("FAILED: std < 5")
        if not pass2: print("FAILED: single component >70%")
        if not pass3: print("FAILED: unique_scores < 10")
        if not pass4: print("FAILED: constant_ratio >5%")
        if not pass5: print("FAILED: same strike >80%")

if __name__ == "__main__":
    main()
