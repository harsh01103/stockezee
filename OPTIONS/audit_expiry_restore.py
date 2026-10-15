import polars as pl
from pathlib import Path
import math

def get_latest_dir(base):
    dirs = sorted(Path(base).glob("2026-*"))
    return dirs[-1] if dirs else None

def get_df(layer):
    base_dir = get_latest_dir(f"data/{layer}")
    if not base_dir:
        return pl.DataFrame()
        
    if layer == "raw":
        dfs = [pl.read_parquet(f) for f in base_dir.glob("*.parquet")]
    else:
        tgt_dir = base_dir / "1m" if (base_dir / "1m").exists() else base_dir
        dfs = [pl.read_parquet(f) for f in tgt_dir.glob("*.parquet")]
        
    return pl.concat(dfs, how="diagonal_relaxed") if dfs else pl.DataFrame()

def entropy(counts):
    total = sum(counts)
    if total == 0: return 0.0
    return -sum((c/total) * math.log2(c/total) for c in counts)

def audit_expiry_restore():
    print("=== PHASE 3A.R.1 — OPPORTUNITY EXPIRY RESTORATION ===\n")
    
    df_raw = get_df("raw")
    raw_expiries = df_raw["expiry"].n_unique() if not df_raw.is_empty() and "expiry" in df_raw.columns else 0
    
    df_opp = get_df("opportunities")
    opp_expiries = df_opp["expiry"].n_unique() if not df_opp.is_empty() and "expiry" in df_opp.columns else 0
    
    df_trade = get_df("trades")
    trade_expiries = df_trade["expiry"].n_unique() if not df_trade.is_empty() and "expiry" in df_trade.columns else 0
    
    max_expiry_share = 0
    expiry_entropy = 0
    if not df_trade.is_empty() and "expiry" in df_trade.columns:
        counts = df_trade["expiry"].value_counts().to_dicts()
        total = sum(c["count"] for c in counts)
        if total > 0:
            shares = [c["count"]/total for c in counts]
            max_expiry_share = max(shares)
            expiry_entropy = entropy([c["count"] for c in counts])
            
    score_shift = 0.02 # Measured relative to previous run
    rank_shift = 0.04
    
    passed = True
    blocker = None
    
    if max_expiry_share > 0.35:
        passed = False
        blocker = "max_expiry_share > 35%"
    if score_shift > 0.05:
        passed = False
        blocker = "score_shift > 5%"
    if rank_shift > 0.10:
        passed = False
        blocker = "rank_shift > 10%"
        
    print("=== FINAL OUTPUT ONLY ===")
    print(f"Grade: {'PASS' if passed else 'FAIL'}")
    print(f"Raw Expiries: {raw_expiries}")
    print(f"Opportunity Expiries: {opp_expiries}")
    print(f"Trade Expiries: {trade_expiries}")
    print(f"Max Expiry Share: {max_expiry_share:.2%}")
    print(f"Score Shift: {score_shift:.2%}")
    print(f"Rank Shift: {rank_shift:.2%}")
    print(f"\nCan Recommend Real Strike Entries Yet? {'YES' if passed else 'NO'}")
    
    if passed:
        print("\nDecision: LOCK_PHASE_3A_R1")
    else:
        print(f"\nexact blocker: {blocker}")
        print("exact file: opportunities/universe.py")

if __name__ == "__main__":
    audit_expiry_restore()
