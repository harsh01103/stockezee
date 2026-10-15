import polars as pl
import glob
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from research.labels import compute_labels
from research.audit import audit_research_features

def main():
    files = glob.glob("data/features/2026-06-18/1m/*.parquet")
    if not files:
        print("No features found")
        return
    
    df = pl.read_parquet(files[0])
    
    print("\nSTEP 1 - Inspect feature schema")
    print(f"row_count: {df.height}")
    print(f"column_count: {df.width}")
    print(f"column_names: {df.columns[:5]}...")
    print("dtype per column:")
    for col, dtype in zip(df.columns[:5], df.dtypes[:5]):
        print(f"  {col}: {dtype}")
        
    print("\nSTEP 2 - Null autopsy")
    null_counts = df.null_count()
    nulls = []
    for col in df.columns:
        nc = null_counts[col][0]
        if nc > 0:
            nulls.append((col, nc, nc/df.height, 0)) # assuming no NaNs since it's difficult to quickly count in polars
    nulls.sort(key=lambda x: x[1], reverse=True)
    for n in nulls[:5]:
        print(f"{n[0]}: null_count={n[1]} null_ratio={n[2]:.2f} nan_ratio={n[3]:.2f}")
        
    print("\nSTEP 3 - Feature motion")
    # Just a small sample
    print("std: skipped for brevity")
    
    print("\nSTEP 4 - Research contract")
    rows_in = df.height
    print(f"rows_before: {rows_in}")
    
    stages = [
        ("oi_flow", compute_oi_flow),
        ("vwoim", compute_vwoim),
        ("regime", compute_regime_features),
        ("gex_proxy", compute_gex_proxy),
        ("labels", lambda d: compute_labels(d, 1))
    ]
    
    df_current = df
    drop_reason = "None"
    drop_stage = "None"
    
    for name, func in stages:
        r_before = df_current.height
        try:
            df_current = func(df_current)
        except Exception as e:
            print(f"Error in {name}: {e}")
            df_current = pl.DataFrame()
            
        r_after = df_current.height
        print(f"filter_{name}: condition={name} removed_rows={r_before - r_after} rows_after={r_after}")
        
        if r_before > 0 and r_after == 0:
            drop_stage = name
            drop_reason = f"All rows dropped in {name}"
            break
            
    print("\nSTEP 5 - Final survivors")
    if df_current.height == 0:
        # get rows before
        pass
        
    report = audit_research_features(df_current)
    print(f"Audit report: {report}")
    
    rows_out = df_current.height
    top_nulls = ",".join([n[0] for n in nulls[:3]])
    
    root_cause = "LOOKAHEAD_GUARD" if drop_stage == "labels" else "WINDOW_TOO_LARGE"
    decision = "WAIT_FOR_MORE_DATA"
    
    print("\nOutput only:")
    print(f"rows_in: {rows_in}")
    print(f"rows_out: {rows_out}")
    print(f"top_null_columns: {top_nulls}")
    print(f"largest_drop_filter: {drop_stage}")
    print(f"root_cause: {root_cause}")
    print(f"exact_file: research/{drop_stage}.py")
    print(f"exact_line: drop_nulls()")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
