import pandas as pl
import polars as pl
import os

def run_forensics():
    file_path = "reports/live_candidates.csv"
    
    if not os.path.exists(file_path):
        print("Candidates: 0")
        print("Publishable: 0")
        print("Top Reject Reason: N/A")
        print("Near Miss Count: 0")
        print("Decision: KEEP_RUNNING")
        print("\nSTOP")
        return

    try:
        df = pl.read_csv(file_path)
    except Exception:
        df = pl.DataFrame()

    if df.height == 0:
        print("Candidates: 0")
        print("Publishable: 0")
        print("Top Reject Reason: N/A")
        print("Near Miss Count: 0")
        print("Decision: KEEP_RUNNING")
        print("\nSTOP")
        return

    total = df.height
    publishable = df.filter(pl.col("publishable") == True).height
    
    reject_counts = df.filter(pl.col("publishable") == False).group_by("reject_reason").agg(pl.len().alias("count")).sort("count", descending=True)
    
    top_reject = "N/A"
    top_pct = 0.0
    if reject_counts.height > 0:
        top_reject = reject_counts["reject_reason"][0]
        top_count = reject_counts["count"][0]
        top_pct = top_count / total
        
    near_miss_conf = df.filter((pl.col("confidence") >= 0.65) & (pl.col("confidence") < 0.75)).height
    near_miss_ttl = df.filter((pl.col("ttl") >= 90) & (pl.col("ttl") < 120)).height
    near_miss_rr = df.filter((pl.col("risk_reward") >= 1.5) & (pl.col("risk_reward") < 1.8)).height
    near_miss_fresh = df.filter((pl.col("freshness") > 5) & (pl.col("freshness") <= 8)).height
    near_miss_spread = df.filter((pl.col("spread") > 0.01) & (pl.col("spread") <= 0.015)).height
    
    near_miss_total = near_miss_conf + near_miss_ttl + near_miss_rr + near_miss_fresh + near_miss_spread
    
    decision = "KEEP_RUNNING"
    if top_pct > 0.7:
        if top_reject == "STALE":
            decision = "PIPELINE_TOO_SLOW"
        elif top_reject == "TTL_TOO_SHORT":
            decision = "TTL_TOO_STRICT"
        elif top_reject == "LOW_CONFIDENCE":
            decision = "EDGE_TOO_WEAK"
        elif top_reject == "SPREAD_TOO_WIDE":
            decision = "MARKET_TOO_WIDE"
        elif top_reject == "POOR_RR":
            decision = "ENTRY_TOO_LATE"

    print(f"Candidates: {total}")
    print(f"Publishable: {publishable}")
    print(f"Top Reject Reason: {top_reject}")
    print(f"Near Miss Count: {near_miss_total}")
    print(f"Decision: {decision}")
    print("\nSTOP")

if __name__ == "__main__":
    run_forensics()
