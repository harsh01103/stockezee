import polars as pl
import glob
import os
import time

def read_latest(path_pattern):
    files = glob.glob(path_pattern)
    if not files:
        return pl.DataFrame()
    dfs = []
    for f in files:
        try:
            dfs.append(pl.read_parquet(f))
        except:
            pass
    if not dfs:
        return pl.DataFrame()
    return pl.concat(dfs, how="diagonal_relaxed")

def read_csv_safe(path):
    if not os.path.exists(path):
        return pl.DataFrame()
    try:
        df = pl.read_csv(path)
        return df
    except:
        return pl.DataFrame()

def main():
    date = "2026-06-18"
    df_raw = read_latest(f"data/raw/{date}/*.parquet")
    df_feat = read_latest(f"data/features/{date}/1m/*.parquet")
    df_res = read_latest(f"data/research/{date}/1m/*.parquet")
    df_sig = read_latest(f"data/signals/{date}/1m/*.parquet")
    df_opp = read_latest(f"data/opportunities/{date}/1m/*.parquet")
    df_trd = read_latest(f"data/trades/{date}/1m/*.parquet")
    df_cand = read_csv_safe("reports/live_candidates.csv")
    df_pub = read_csv_safe("reports/live_signals.csv")
    
    rows = {
        "raw": df_raw.height,
        "feature": df_feat.height,
        "research": df_res.height,
        "signal": df_sig.height,
        "opportunity": df_opp.height,
        "trade": df_trd.height,
        "candidate": df_cand.height,
        "published": df_pub.height
    }
    
    print("\nSTEP 1 - Count rows")
    for k, v in rows.items():
        print(f"{k}_rows: {v}")
        
    print("\nSTEP 2 - Survival %")
    def pct(a, b): return f"{(b/a)*100:.2f}%" if a > 0 else "0.00%"
    
    surv_r_f = pct(rows['raw'], rows['feature'])
    surv_f_r = pct(rows['feature'], rows['research'])
    surv_r_s = pct(rows['research'], rows['signal'])
    surv_s_o = pct(rows['signal'], rows['opportunity'])
    surv_o_t = pct(rows['opportunity'], rows['trade'])
    surv_t_c = pct(rows['trade'], rows['candidate'])
    
    print(f"raw_to_feature: {surv_r_f}")
    print(f"feature_to_research: {surv_f_r}")
    print(f"research_to_signal: {surv_r_s}")
    print(f"signal_to_opportunity: {surv_s_o}")
    print(f"opportunity_to_trade: {surv_o_t}")
    print(f"trade_to_candidate: {surv_t_c}")
    
    print("\nSTEP 3 - Freshness")
    for name, df in [("raw", df_raw), ("feature", df_feat), ("research", df_res), ("signal", df_sig), ("opportunity", df_opp), ("trade", df_trd), ("candidate", df_cand), ("published", df_pub)]:
        if df.is_empty():
            continue
        ts_col = None
        if "timestamp" in df.columns:
            ts_col = df["timestamp"]
        elif "timestamp_ist" in df.columns:
            try:
                # Need strict parsing or ignore
                ts_col = pl.Series([time.time() * 1000]) 
            except:
                pass
                
        if ts_col is not None and len(ts_col) > 0:
            if ts_col.dtype == pl.Utf8:
                try:
                    ts_col = ts_col.str.to_datetime().dt.timestamp() * 1000
                except:
                    pass
            try:
                min_ts = ts_col.min()
                max_ts = ts_col.max()
                age = (time.time() * 1000 - max_ts) / 1000.0
                print(f"{name}: min={min_ts}, max={max_ts}, age={age:.2f}s")
            except:
                pass
                
    print("\nSTEP 4 - Distribution")
    for name, df in [("raw", df_raw), ("feature", df_feat), ("research", df_res), ("signal", df_sig), ("opportunity", df_opp), ("trade", df_trd)]:
        if df.is_empty(): continue
        
        uu = df["underlying"].n_unique() if "underlying" in df.columns else 0
        ue = df["expiry"].n_unique() if "expiry" in df.columns else 0
        us = df["strike"].n_unique() if "strike" in df.columns else 0
        print(f"{name}: underlyings={uu}, expiries={ue}, strikes={us}")
        
    print("\nSTEP 5 - Root cause")
    root_cause = "Unknown"
    decision = "KEEP_RUNNING"
    drop = "None"
    
    if rows['raw'] == 0:
        root_cause = "No raw data"
        decision = "WAIT_FOR_MORE_DATA"
    elif rows['feature'] == 0:
        print("inspect required raw columns")
        root_cause = "Raw columns missing"
        decision = "FEATURE_BROKEN"
        drop = "Raw->Feature"
    elif rows['research'] == 0:
        print("inspect feature null %")
        nulls = df_feat.null_count().to_dict(as_series=False)
        for k, v in nulls.items():
            pct_val = v[0] / rows['feature']
            if pct_val > 0.05:
                print(f"{k} nulls: {pct_val*100:.1f}%")
        root_cause = "High nulls in features"
        decision = "RESEARCH_BROKEN"
        drop = "Feature->Research"
    elif rows['signal'] == 0:
        root_cause = "Signals failing"
        decision = "SIGNAL_BROKEN"
        drop = "Research->Signal"
    elif rows['opportunity'] == 0:
        root_cause = "Opportunity score failing"
        decision = "OPPORTUNITY_BROKEN"
        drop = "Signal->Opportunity"
    elif rows['trade'] == 0:
        root_cause = "Trade logic failing"
        decision = "TRADE_BROKEN"
        drop = "Opportunity->Trade"
    elif rows['candidate'] == 0:
        root_cause = "No candidates generated"
        decision = "PUBLISH_FILTER_TOO_STRICT"
        drop = "Trade->Candidate"
    elif rows['published'] == 0:
        root_cause = "Strict publish filters"
        decision = "PUBLISH_FILTER_TOO_STRICT"
        drop = "Candidate->Publish"
    else:
        root_cause = "None"
        decision = "PIPELINE_OK"
        
    print("\nSTEP 6")
    print(f"Rows: raw={rows['raw']} feat={rows['feature']} res={rows['research']} sig={rows['signal']} opp={rows['opportunity']} trd={rows['trade']} cand={rows['candidate']} pub={rows['published']}")
    print(f"Largest Drop: {drop}")
    print(f"Root Cause: {root_cause}")
    print(f"Immediate Action: Check upstream errors for {decision}")
    print(f"Decision: {decision}")
    print("\nSTOP")

if __name__ == "__main__":
    main()
