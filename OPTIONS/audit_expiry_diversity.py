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

def audit_expiry_diversity():
    print("=== PHASE 3A.R — EXPIRY DIVERSIFICATION CERTIFICATION ===\n")
    
    # 1. RAW
    print("=== STEP 1 — RAW LAYER ===")
    df_raw = get_df("raw")
    if df_raw.is_empty(): return
    raw_expiries = df_raw["expiry"].value_counts().to_dicts() if "expiry" in df_raw.columns else []
    raw_c = {r["expiry"]: r["count"] for r in raw_expiries}
    raw_unique = len(raw_c)
    raw_entropy = entropy(list(raw_c.values()))
    print(f"unique_expiries: {raw_unique}")
    print(f"expiry_entropy: {raw_entropy:.2f}")
    
    # 2. FEATURES
    print("\n=== STEP 2 — FEATURE LAYER ===")
    df_feat = get_df("features")
    if df_feat.is_empty(): return
    feat_expiries = df_feat["expiry"].value_counts().to_dicts() if "expiry" in df_feat.columns else []
    feat_c = {r["expiry"]: r["count"] for r in feat_expiries}
    feat_unique = len(feat_c)
    print(f"unique_expiries: {feat_unique}")
    
    # 3. RESEARCH
    print("\n=== STEP 3 — RESEARCH LAYER ===")
    df_res = get_df("research")
    if df_res.is_empty(): return
    res_expiries = df_res["expiry"].value_counts().to_dicts() if "expiry" in df_res.columns else []
    res_c = {r["expiry"]: r["count"] for r in res_expiries}
    res_unique = len(res_c)
    print(f"unique_expiries: {res_unique}")
    
    # 4. SIGNALS
    print("\n=== STEP 4 — SIGNAL LAYER ===")
    df_sig = get_df("signals")
    if df_sig.is_empty(): return
    sig_expiries = df_sig["expiry"].value_counts().to_dicts() if "expiry" in df_sig.columns else []
    sig_c = {r["expiry"]: r["count"] for r in sig_expiries}
    sig_unique = len(sig_c)
    print(f"unique_expiries: {sig_unique}")
    
    # 5. OPPORTUNITIES
    print("\n=== STEP 5 — OPPORTUNITY LAYER ===")
    df_opp = get_df("opportunities")
    if df_opp.is_empty(): return
    opp_expiries = df_opp["expiry"].value_counts().to_dicts() if "expiry" in df_opp.columns else []
    opp_c = {r["expiry"]: r["count"] for r in opp_expiries}
    opp_unique = len(opp_c)
    print(f"unique_expiries: {opp_unique}")
    
    # 6. TRADES
    print("\n=== STEP 6 — TRADE LAYER ===")
    df_trade = get_df("trades")
    if df_trade.is_empty(): return
    trade_expiries = df_trade["expiry"].value_counts().to_dicts() if "expiry" in df_trade.columns else []
    trade_c = {r["expiry"]: r["count"] for r in trade_expiries}
    trade_unique = len(trade_c)
    print(f"unique_expiries: {trade_unique}")
    
    # Determine Drop
    root_layer = None
    exact_file = None
    
    if raw_unique < 2:
        root_layer = "RAW_CAPTURE"
        exact_file = "market/recorder.py"
    elif feat_unique < raw_unique:
        root_layer = "FEATURE_COLLAPSE"
        exact_file = "features/builder.py"
    elif res_unique < feat_unique:
        root_layer = "RESEARCH_COLLAPSE"
        exact_file = "research/builder.py"
    elif sig_unique < res_unique:
        root_layer = "SIGNAL_SELECTION"
        exact_file = "signals/builder.py"
    elif opp_unique < sig_unique and opp_unique == 1:
        root_layer = "OPPORTUNITY_FILTER"
        exact_file = "opportunities/universe.py"
    elif trade_unique < opp_unique:
        root_layer = "TRADE_CONSTRUCTOR"
        exact_file = "trade/constructor.py"
    else:
        # If it dropped at opps but is still > 1, check if we lost 20%
        if opp_unique < raw_unique:
            root_layer = "OPPORTUNITY_FILTER"
            exact_file = "opportunities/universe.py"

    entropy_loss = raw_entropy - entropy(list(trade_c.values()))

    print("\n=== FINAL OUTPUT ONLY ===")
    if root_layer or trade_unique < 2:
        if not root_layer:
            root_layer = "RAW_CAPTURE" if raw_unique < 2 else "UNKNOWN"
            exact_file = "market/recorder.py" if raw_unique < 2 else "UNKNOWN"
            
        print("Grade: FAIL")
        print(f"Raw Expiries: {raw_unique}")
        print(f"Final Expiries: {trade_unique}")
        print(f"Entropy Loss: {entropy_loss:.2f}")
        print(f"Root Layer: {root_layer}")
        print(f"Exact File: {exact_file}")
        print("Exact Metric: unique_expiries")
        print("\nDecision: STOP")
    else:
        print("Grade: PASS")
        print(f"Raw Expiries: {raw_unique}")
        print(f"Final Expiries: {trade_unique}")
        print(f"Entropy Loss: {entropy_loss:.2f}")
        print("Root Layer: N/A")
        print("Exact File: N/A")
        print("Exact Metric: N/A")
        print("\nDecision: LOCK_EXPIRY_DIVERSITY")

if __name__ == "__main__":
    audit_expiry_diversity()
