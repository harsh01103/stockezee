"""PHASE O2I — ENTRY VALIDATION"""
import glob, os, csv, polars as pl
from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from opportunities.scorer import score_opportunities
from opportunities.universe import build_universe
from opportunities.ranker import rank_opportunities
from opportunities.confidence import calculate_confidence
import logging
logging.getLogger("universe").setLevel(logging.ERROR)

date_str = "2026-06-19"
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed")

res = process_features(df_raw, date_str, dry_run=False)
df_res = compute_gex_proxy(compute_regime_features(compute_vwoim(compute_oi_flow(res["df_features"]))))
df_res = df_res.sort("timestamp")

pk = ["underlying", "expiry", "strike", "option_type"]
def zscore(col):
    return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
           (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
features = []
if "vwoim_smoothed" in df_res.columns:
    df_res = df_res.with_columns(zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"))
    features.append("z_vwoim")
if "oi_flow_score" in df_res.columns:
    df_res = df_res.with_columns(zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"))
    features.append("z_oi_flow")
if "gex_proxy" in df_res.columns:
    df_res = df_res.with_columns(zscore("gex_proxy").fill_null(0).alias("z_gex"))
    features.append("z_gex")
df_res = df_res.with_columns(pl.sum_horizontal(features).alias("raw_score"))
df_res = df_res.with_columns(
    (pl.col("raw_score") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
)

# Full pipeline — collect ALL candidates (not just published) with timestamps
all_cands = []
for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)
df_all = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()

# Load top executable contracts from previous phase
exec_csv = pl.read_csv("reports/executable_trade_ideas.csv")
exec_keys = []
for r in exec_csv.head(21).iter_rows(named=True):
    exec_keys.append({
        "underlying": r["underlying"],
        "expiry": r["expiry"],
        "strike": float(r["strike"]),
        "option_type": r["option_type"],
    })

print("Tracking " + str(len(exec_keys)) + " executable contracts across all timestamps")
print("Total candidate observations: " + str(df_all.height))

# For each executable contract, trace its confidence history
results = []
for ek in exec_keys:
    mask = (
        (df_all["underlying"] == ek["underlying"]) &
        (df_all["expiry"] == ek["expiry"]) &
        (df_all["strike"] == ek["strike"]) &
        (df_all["option_type"] == ek["option_type"])
    )
    df_contract = df_all.filter(mask).sort("timestamp")
    
    if df_contract.is_empty():
        results.append({
            "underlying": ek["underlying"], "expiry": ek["expiry"],
            "strike": ek["strike"], "option_type": ek["option_type"],
            "first_seen": "", "last_seen": "", "active_minutes": 0,
            "peak_confidence": 0, "median_confidence": 0, "confidence_std": 0,
            "peak_volume": 0, "median_spread": 0,
            "direction_consistency": 0, "status": "NOT_FOUND",
        })
        continue
    
    timestamps = df_contract["timestamp"].to_list()
    first_ts = min(timestamps)
    last_ts = max(timestamps)
    active_minutes = round((last_ts - first_ts) / 60000, 1)
    
    confs = df_contract["confidence"].to_list()
    peak_conf = max(confs)
    median_conf = float(df_contract["confidence"].median())
    conf_std = float(df_contract["confidence"].std()) if len(confs) > 1 else 0.0
    
    peak_vol = float(df_contract["volume"].max()) if "volume" in df_contract.columns else 0
    median_spr = float(df_contract["spread"].median()) if "spread" in df_contract.columns else 0
    
    # Direction consistency: fraction of observations above 0.75
    above_075 = len([c for c in confs if c >= 0.75])
    direction_consistency = round(above_075 / len(confs), 4) if confs else 0
    
    # Spread expansion check
    spreads = df_contract["spread"].to_list() if "spread" in df_contract.columns else []
    spreads_clean = [s for s in spreads if s is not None and s > 0]
    if len(spreads_clean) >= 2:
        first_spread = spreads_clean[0]
        last_spread = spreads_clean[-1]
        spread_expanded = last_spread > 2 * first_spread if first_spread > 0 else False
    else:
        spread_expanded = False
    
    # Status determination
    if active_minutes < 10:
        status = "UNSTABLE_SHORT"
    elif conf_std > 0.20:
        status = "UNSTABLE_VOLATILE"
    elif spread_expanded:
        status = "UNSTABLE_SPREAD"
    else:
        status = "STABLE"
    
    results.append({
        "underlying": ek["underlying"], "expiry": ek["expiry"],
        "strike": ek["strike"], "option_type": ek["option_type"],
        "first_seen": round(first_ts, 0), "last_seen": round(last_ts, 0),
        "active_minutes": active_minutes,
        "peak_confidence": round(peak_conf, 4),
        "median_confidence": round(median_conf, 4),
        "confidence_std": round(conf_std, 4),
        "peak_volume": round(peak_vol, 0),
        "median_spread": round(median_spr, 4),
        "direction_consistency": direction_consistency,
        "status": status,
    })

# Sort by peak confidence descending
results.sort(key=lambda x: x["peak_confidence"], reverse=True)

# Display top 10
print("\n=== TOP 10 EXECUTABLE CONTRACT STABILITY ===")
hdr = "RK  UNDERLYING  EXPIRY      STRIKE    TYPE  ACTIVE_MIN  PEAK_CONF  MED_CONF  CONF_STD  PEAK_VOL      MED_SPR   DIR_CONS  STATUS"
print(hdr)
print("-" * len(hdr))
for idx, r in enumerate(results[:10]):
    line = str(idx+1).ljust(4)
    line += str(r["underlying"]).ljust(12)
    line += str(r["expiry"]).ljust(12)
    line += str(r["strike"]).ljust(10)
    line += str(r["option_type"]).ljust(6)
    line += str(r["active_minutes"]).ljust(12)
    line += str(r["peak_confidence"]).ljust(11)
    line += str(r["median_confidence"]).ljust(10)
    line += str(r["confidence_std"]).ljust(10)
    line += str(int(r["peak_volume"])).ljust(14)
    line += str(r["median_spread"]).ljust(10)
    line += str(r["direction_consistency"]).ljust(10)
    line += r["status"]
    print(line)

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/entry_validation.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

# Summary
stable = [r for r in results if r["status"] == "STABLE"]
unstable = [r for r in results if r["status"] != "STABLE"]

stable_contracts = len(stable)
unstable_contracts = len(unstable)
best_stable = stable[0] if stable else None
best_stable_name = (best_stable["underlying"] + " " + str(best_stable["expiry"]) + " " + 
                    str(best_stable["strike"]) + " " + best_stable["option_type"]) if best_stable else "NONE"
best_stable_conf = best_stable["peak_confidence"] if best_stable else 0

if stable_contracts == 0:
    decision = "WAIT"
elif stable_contracts <= 3:
    decision = "SELECTIVE_ENTRY"
else:
    decision = "ENTRY_READY"

print("\nOUTPUT:")
print("stable_contracts: " + str(stable_contracts))
print("unstable_contracts: " + str(unstable_contracts))
print("best_stable_contract: " + best_stable_name)
print("best_stable_confidence: " + str(best_stable_conf))
print("decision: " + decision)
print("STOP")
