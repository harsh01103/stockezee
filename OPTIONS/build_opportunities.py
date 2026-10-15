import argparse
import sys
from datetime import datetime
from pathlib import Path
import polars as pl
import json

from opportunities.universe import build_universe
from opportunities.scorer import score_opportunities
from opportunities.ranker import rank_opportunities
from opportunities.zones import calculate_zones
from opportunities.confidence import calculate_confidence

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    date_str = args.date
    base_dir = Path(f"data/signals/{date_str}")
    
    if not base_dir.exists():
        print(f"No signals data found for {date_str}")
        sys.exit(1)
        
    candidate_count = 0
    avg_score = 0.0
    top_opps = []
    confidence_dist = {}
    
    # Process 1m data as primary source
    interval_dir = base_dir / "1m"
    if not interval_dir.exists():
        print("No 1m data found")
        sys.exit(1)
        
    files = list(interval_dir.glob("*.parquet"))
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    
    # 1. Candidate Universe
    df = build_universe(df)
    candidate_count = df.height
    
    if candidate_count == 0:
        passed = False
        blocker = "candidate_count == 0"
    else:
        # 2. Score Engine
        df = score_opportunities(df)
        
        # Reject negative scores
        if df.filter(pl.col("opportunity_score") < 0).height > 0:
            passed = False
            blocker = "negative scores generated"
        else:
            # 3. Strike Ranking
            df = rank_opportunities(df)
            
            # 4 & 5. Entry Zones & Exits
            df = calculate_zones(df)
            
            # 6. Confidence
            df_conf = calculate_confidence(df)
            
            # If after confidence filtering all are dropped (confidence > 0.95 rejected them all)
            if df_conf.height == 0 and df.height > 0:
                passed = False
                blocker = "All opportunities rejected due to confidence > 0.95"
            else:
                df = df_conf
                avg_score = df.select(pl.col("opportunity_score").mean()).item()
                
                # Extract top opportunities for reporting
                # We can sort by opportunity_score and take the top 5
                top_df = df.sort("opportunity_score", descending=True).head(5)
                
                pk = ["underlying", "expiry", "strike", "option_type"]
                for row in top_df.iter_rows(named=True):
                    name_parts = []
                    for c in pk:
                        if c in row and row[c] is not None:
                            name_parts.append(str(row[c]))
                    name = "_".join(name_parts) if name_parts else "Mock_Opp"
                    top_opps.append({
                        "instrument": name,
                        "score": row.get("opportunity_score", 0.0),
                        "rank": row.get("rank", 1.0),
                        "confidence": row.get("confidence", 0.0)
                    })
                    
                # Confidence distribution
                conf_list = df["confidence"].drop_nulls().to_list()
                if conf_list:
                    confidence_dist = {
                        "min": min(conf_list),
                        "max": max(conf_list),
                        "mean": sum(conf_list) / len(conf_list)
                    }
                    
                # Output
                out_dir = Path(f"data/opportunities/{date_str}/1m")
                out_dir.mkdir(parents=True, exist_ok=True)
                df.write_parquet(out_dir / f"opportunities_{date_str}.parquet")
                
                passed = True
                blocker = ""
                
    report = {
        "grade": "PASS" if passed else "FAIL",
        "candidate_count": candidate_count,
        "avg_score": avg_score,
        "top_opportunities": top_opps,
        "confidence_distribution": confidence_dist
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase3a.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Candidate Count: {report['candidate_count']}")
    print(f"Avg Score: {report['avg_score']:.2f}")
    
    if passed:
        print("\nPASS")
        print("PHASE 3A COMPLETE")
    else:
        print("\nFAIL")
        print(f"EXACT BLOCKER: {blocker}")

if __name__ == "__main__":
    main()
