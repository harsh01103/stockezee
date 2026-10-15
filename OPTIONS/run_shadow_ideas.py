"""
PHASE O2B — SHADOW TRADE IDEAS SNAPSHOT
"""
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

date_str = "2026-06-19"
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
print(f"Parquet files: {len(raw_files)}")
dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed")
print(f"Total rows: {df_raw.height}")

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

# Run pipeline for every timestamp
all_cands = []
for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)

df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()
print(f"Total candidates: {df_out.height}")

if df_out.is_empty():
    print("NO CANDIDATES")
    exit()

# Get z-scores joined back
z_cols = [c for c in ["z_vwoim", "z_oi_flow", "z_gex"] if c in df_res.columns]
join_cols = ["timestamp", "underlying", "expiry", "strike", "option_type"]
avail_join = [c for c in join_cols if c in df_out.columns and c in df_res.columns]
z_source = df_res.select(avail_join + z_cols).unique(subset=avail_join, keep="last")
df_merged = df_out.join(z_source, on=avail_join, how="left", suffix="_r")

def bucket(conf):
    if conf >= 0.75: return "EXECUTABLE"
    elif conf >= 0.70: return "NEAR_SIGNAL"
    elif conf >= 0.60: return "WATCHLIST"
    else: return "WEAK"

def reason(conf):
    if conf >= 0.75: return "NONE"
    elif conf >= 0.70: return "BELOW_PUBLISH_THRESHOLD"
    elif conf >= 0.60: return "CONFIDENCE_TOO_LOW"
    else: return "WEAK_SIGNAL"

# Top 10 by confidence
top10 = df_merged.sort("confidence", descending=True).head(10)

print()
header = f"{'RANK':<5} {'UNDERLYING':<12} {'EXPIRY':<12} {'STRIKE':<8} {'TYPE':<5} {'CONF':<10} {'SPREAD':<10} {'VOL':<10} {'Z_VWOIM':<10} {'Z_OI':<10} {'Z_GEX':<10} {'BUCKET':<15} REASON"
print("=" * len(header))
print(header)
print("=" * len(header))

rows_csv = []
for idx in range(top10.height):
    r = top10.row(idx, named=True)
    conf = r.get("confidence", 0)
    b = bucket(conf)
    rsn = reason(conf)
    z_v = r.get("z_vwoim", r.get("z_vwoim_r", 0)) or 0
    z_o = r.get("z_oi_flow", r.get("z_oi_flow_r", 0)) or 0
    z_g = r.get("z_gex", r.get("z_gex_r", 0)) or 0
    spr = r.get("spread", 0) or 0
    vol = r.get("volume", 0) or 0
    rr_val = r.get("rr", r.get("risk_reward", 0)) or 0

    print(f"{idx+1:<5} {str(r.get('underlying','?')):<12} {str(r.get('expiry','?')):<12} {str(r.get('strike','?')):<8} {str(r.get('option_type','?')):<5} {conf:<10.4f} {spr:<10.2f} {vol:<10.0f} {z_v:<10.4f} {z_o:<10.4f} {z_g:<10.4f} {b:<15} {rsn}")

    rows_csv.append({
        "timestamp": r.get("timestamp", ""),
        "underlying": r.get("underlying", ""),
        "expiry": str(r.get("expiry", "")),
        "strike": r.get("strike", ""),
        "option_type": r.get("option_type", ""),
        "confidence": round(conf, 4),
        "rr": round(rr_val, 4),
        "spread": round(spr, 4),
        "volume": round(vol, 2),
        "z_vwoim": round(z_v, 4),
        "z_oi_flow": round(z_o, 4),
        "z_gex": round(z_g, 4),
        "bucket": b,
        "reason_not_published": rsn,
    })

print("=" * len(header))

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/shadow_trade_ideas.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows_csv[0].keys())
    writer.writeheader()
    writer.writerows(rows_csv)

best = rows_csv[0]
published = sum(1 for r in rows_csv if r["bucket"] == "EXECUTABLE")

if best["confidence"] >= 0.75:
    decision = "EXECUTABLE_EXISTS"
elif best["confidence"] >= 0.70:
    decision = "ALMOST_READY"
else:
    decision = "WATCH_ONLY"

print()
print("OUTPUT:")
print(f"tracker: STOPPED")
print(f"ideas_generated: {len(rows_csv)}")
print(f"best_confidence: {best['confidence']:.4f}")
print(f"best_trade: {best['underlying']} {best['expiry']} {best['strike']} {best['option_type']}")
print(f"best_bucket: {best['bucket']}")
print(f"published: {published}")
print(f"decision: {decision}")
print("STOP")
