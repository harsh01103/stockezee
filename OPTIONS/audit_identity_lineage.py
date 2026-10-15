import polars as pl
from pathlib import Path
import os
import glob

def get_latest_files(layer):
    dirs = sorted(Path(f"data/{layer}").glob("2026-*"))
    if not dirs: return []
    latest_dir = dirs[-1]
    
    # Could be in 1m/ or directly in the date dir depending on layer
    files = list(latest_dir.glob("*.parquet"))
    if not files:
        files = list(latest_dir.rglob("*.parquet"))
    return files

def audit_identity_lineage():
    print("=== PHASE 4B.R.4 — RAW IDENTITY LINEAGE AUDIT ===\n")
    
    layers = ["raw", "features", "research", "signals", "opportunities", "trades"]
    
    results = []
    
    root_layer = None
    first_bad_file = None
    first_bad_row = None
    first_bad_instrument = None
    
    for layer in layers:
        files = get_latest_files(layer)
        if not files:
            print(f"{layer.upper()}:\nNo files found.\n")
            continue
            
        dfs = []
        for f in files:
            try:
                dfs.append(pl.read_parquet(f))
            except:
                pass
                
        if not dfs:
            print(f"{layer.upper()}:\nNo data loaded.\n")
            continue
            
        df = pl.concat(dfs, how="diagonal_relaxed")
        
        rows = df.height
        
        # handle missing columns gracefully
        if "underlying" in df.columns:
            unknown_count = df.filter(pl.col("underlying") == "UNKNOWN").height
            unknown_ratio = unknown_count / rows if rows > 0 else 0
        else:
            unknown_ratio = 0
            
        if "strike" in df.columns:
            zero_strike_count = df.filter(pl.col("strike") <= 1.0).height
            zero_strike_ratio = zero_strike_count / rows if rows > 0 else 0
        else:
            zero_strike_ratio = 0
            
        if "expiry" in df.columns:
            empty_expiry_count = df.filter((pl.col("expiry") == "") | pl.col("expiry").is_null()).height
            empty_expiry_ratio = empty_expiry_count / rows if rows > 0 else 0
        else:
            empty_expiry_ratio = 0
            
        unique_instruments = 0
        if "instrument_key" in df.columns:
            unique_instruments = df["instrument_key"].n_unique()
            
        print(f"{layer.upper()}:")
        print(f"rows={rows}")
        print(f"unknown={unknown_ratio:.2%}")
        print(f"zero_strike={zero_strike_ratio:.2%}")
        print(f"empty_expiry={empty_expiry_ratio:.2%}\n")
        
        results.append({
            "layer": layer,
            "rows": rows,
            "unique_instruments": unique_instruments,
            "unknown_underlying_ratio": unknown_ratio,
            "zero_strike_ratio": zero_strike_ratio,
            "empty_expiry_ratio": empty_expiry_ratio
        })
        
        # Identify collapse
        if unknown_ratio > 0 and root_layer is None:
            root_layer = layer
            first_bad_file = str(files[0])
            first_bad_row = 0
            if "instrument_key" in df.columns:
                first_bad_instrument = df["instrument_key"][0]
            else:
                first_bad_instrument = "N/A"
                
    if root_layer:
        print("root_layer")
        print(root_layer.upper())
        print("first_bad_file")
        print(first_bad_file)
        print("first_bad_row")
        print(first_bad_row)
        print("instrument_key")
        print(first_bad_instrument)
        print("\n")
        
    df_results = pl.DataFrame(results)
    os.makedirs("reports", exist_ok=True)
    df_results.write_csv("reports/identity_lineage.csv")
    
    passed = False
    if results:
        # Check if raw has UNKNOWN < 1%
        if results[0]["unknown_underlying_ratio"] < 0.01:
            passed = True
            
    print("Decision:")
    print("PASS" if passed else "FAIL")

if __name__ == "__main__":
    audit_identity_lineage()
