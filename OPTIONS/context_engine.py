import glob
import os
import polars as pl

def fetch_global_context(ts):
    return {
        "status": "UNAVAILABLE",
        "block_context": True,
        "global_risk": 1.0,
        "source_type": "UNKNOWN"
    }

def fetch_macro_context(ts):
    return {
        "status": "UNAVAILABLE",
        "block_context": True,
        "macro_risk": 1.0,
        "source_type": "UNKNOWN"
    }

def fetch_news_context(ts):
    return {
        "status": "UNAVAILABLE",
        "block_context": True,
        "news_risk": 1.0,
        "source_type": "UNKNOWN"
    }

def compute_nse_context(df_ts: pl.DataFrame):
    if df_ts.is_empty():
        return {"pcr": 1.0, "oi_regime": "unwind"}
        
    calls = df_ts.filter(pl.col("option_type") == "CE")
    puts = df_ts.filter(pl.col("option_type") == "PE")
    
    total_call_oi = calls["oi"].sum()
    total_put_oi = puts["oi"].sum()
    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
    
    # Simple OI buildup classification based on mock delta
    delta_oi = df_ts["delta_oi"].sum() if "delta_oi" in df_ts.columns else 0
    delta_price = (df_ts["ask"].mean() - df_ts["bid"].mean()) if "ask" in df_ts.columns else 0.0
    
    if delta_oi > 0 and delta_price > 0:
        oi_regime = "long buildup"
    elif delta_oi > 0 and delta_price < 0:
        oi_regime = "short buildup"
    elif delta_oi < 0 and delta_price < 0:
        oi_regime = "long unwind"
    else:
        oi_regime = "short covering"
        
    return {
        "pcr": pcr,
        "oi_regime": oi_regime
    }

def generate_context():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    
    dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
    if not dfs:
        print("No raw data found.")
        return
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    timestamps = sorted(df_raw["timestamp"].unique().to_list())
    
    records = []
    
    for ts in timestamps:
        df_ts = df_raw.filter(pl.col("timestamp") == ts)
        
        nse_ctx = compute_nse_context(df_ts)
        glob_ctx = fetch_global_context(ts)
        mac_ctx = fetch_macro_context(ts)
        news_ctx = fetch_news_context(ts)
        
        # Runtime Guard
        if glob_ctx.get("source_type") not in ["REAL", "DERIVED_FROM_REAL"]:
            raise RuntimeError("Missing real external data source")
            
        if mac_ctx.get("source_type") not in ["REAL", "DERIVED_FROM_REAL"]:
            raise RuntimeError("Missing real external data source")
            
        if news_ctx.get("source_type") not in ["REAL", "DERIVED_FROM_REAL"]:
            raise RuntimeError("Missing real external data source")
            
        
        # Simple risk aggregation
        market_context_score = 1.0 - max(glob_ctx["global_risk"], mac_ctx["macro_risk"], news_ctx["news_risk"])
        
        # Risk mode logic
        if market_context_score < 0.5:
            risk_mode = "RED"
            explanation = "Macro/Global Risk Elevated"
        elif market_context_score < 0.8:
            risk_mode = "YELLOW"
            explanation = "Moderate Risk Environment"
        else:
            risk_mode = "GREEN"
            explanation = "Normal Environment"
            
        # Overwrite with NSE specifics just to simulate
        if nse_ctx["pcr"] < 0.5:
            risk_mode = "YELLOW"
            explanation = "Low PCR Caution"
            
        records.append({
            "timestamp": ts,
            "market_context_score": market_context_score,
            "risk_mode": risk_mode,
            "oi_regime": nse_ctx["oi_regime"],
            "macro_risk": mac_ctx["macro_risk"],
            "news_risk": news_ctx["news_risk"],
            "global_risk": glob_ctx["global_risk"],
            "explanation": explanation
        })
        
    df_out = pl.DataFrame(records)
    
    os.makedirs("reports", exist_ok=True)
    df_out.write_csv("reports/context_log.csv")
    
    records_created = df_out.height
    green_pct = df_out.filter(pl.col("risk_mode") == "GREEN").height / records_created * 100.0 if records_created > 0 else 0
    yellow_pct = df_out.filter(pl.col("risk_mode") == "YELLOW").height / records_created * 100.0 if records_created > 0 else 0
    red_pct = df_out.filter(pl.col("risk_mode") == "RED").height / records_created * 100.0 if records_created > 0 else 0
    
    top_block_df = df_out.filter(pl.col("risk_mode") == "RED")
    if top_block_df.height > 0:
        top_block_reason = top_block_df.group_by("explanation").len().sort("len", descending=True).head(1)["explanation"].item()
    else:
        top_block_reason = "NONE"
        
    print("\nOUTPUT:")
    print(f"records_created: {records_created}")
    print(f"green_pct: {green_pct:.2f}%")
    print(f"yellow_pct: {yellow_pct:.2f}%")
    print(f"red_pct: {red_pct:.2f}%")
    print(f"top_block_reason: {top_block_reason}")
    print("decision: CONTEXT_READY")
    print("STOP")

if __name__ == "__main__":
    generate_context()
