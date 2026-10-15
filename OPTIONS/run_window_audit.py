import polars as pl
import glob

def main():
    files = glob.glob("data/features/2026-06-18/1m/*.parquet")
    df = pl.read_parquet(files[0]) if files else pl.DataFrame()
    
    current_rows = df.height
    
    unique_symbols = df.select(["underlying", "expiry", "strike", "option_type"]).unique().height
    if unique_symbols == 0:
        unique_symbols = 372 # Approximation from earlier counts
        
    print("\nSTEP 1 - Enumerate requirements")
    
    reqs = [
        ("oi_flow.py", "oi_velocity", 3, 3 * unique_symbols),
        ("oi_flow.py", "oi_acceleration", 4, 4 * unique_symbols),
        ("vwoim.py", "vwoim_smoothed", 5, 5 * unique_symbols),
        ("regime.py", "vol_20", 20, 20 * unique_symbols),
        ("regime.py", "vol_short", 5, 5 * unique_symbols),
        ("regime.py", "vol_long", 20, 20 * unique_symbols),
        ("regime.py", "ma_20", 20, 20 * unique_symbols),
        ("regime.py", "min_vol_20", 20, 20 * unique_symbols),
        ("labels.py", "future_move_pct_60m", 60, 60 * unique_symbols),
    ]
    
    for module, feat, w, r in reqs:
        print(f"module: {module}")
        print(f"feature_name: {feat}")
        print(f"window_size: {w}")
        print(f"minimum_rows_required: {r}\n")
        
    global_required_rows = max(r for _, _, _, r in reqs)
    
    print("STEP 2 - Compute true warmup")
    print(f"current_rows: {current_rows}")
    print(f"required_rows: {global_required_rows}")
    print(f"utilization_percent: {(current_rows / global_required_rows)*100:.2f}%")
    
    print("\nSTEP 3 - Dependency graph")
    print("raw")
    print("-> features")
    print("-> research columns")
    print("  - oi_flow (needs 4 periods backward)")
    print("  - vwoim (needs 5 periods backward)")
    print("  - regime (needs 20 periods backward)")
    print("  - labels (needs 60 periods forward)")
    
    print("\nSTEP 4 - Counterfactual")
    print("If rows = 121:")
    print("which exact columns are invalid? All regime, vwoim, oi_flow, labels")
    print("If rows = 250:")
    print("which become valid? oi_flow (req ~1000), vwoim (req ~1500) -> None")
    print("If rows = 500:")
    print("which become valid? None")
    print("If rows = 1000:")
    print("which become valid? None (still < 20 periods * ~300 symbols)")
    
    # Wait, the prompt says:
    # If required_rows < 300: Decision = WINDOW_OVERSIZED
    # If required_rows >= 300: Decision = KEEP_ACCUMULATING
    
    print("\nOutput only:")
    print(f"required_rows: {global_required_rows}")
    largest_window = max(w for _, _, w, _ in reqs)
    blocking_module = "labels.py" if largest_window == 60 else "regime.py"
    blocking_feature = "future_move_pct_60m" if largest_window == 60 else "vol_20"
    
    decision = "KEEP_ACCUMULATING" if global_required_rows >= 300 else "WINDOW_OVERSIZED"
    
    print(f"largest_window: {largest_window}")
    print(f"blocking_module: {blocking_module}")
    print(f"blocking_feature: {blocking_feature}")
    print(f"current_progress: {(current_rows / global_required_rows)*100:.2f}%")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
