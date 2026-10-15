"""PHASE O2G — PUBLISHED SIGNAL SANITY (REAL DATA ONLY)"""
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
print("Raw rows: " + str(df_raw.height))

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

# Full pipeline per timestamp
all_cands = []
for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)

df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()

# STEP 1: Filter published
df_pub = df_out.filter(pl.col("confidence") >= 0.75)
published_count = df_pub.height
print("Published count: " + str(published_count))

if published_count == 0:
    print("\nOUTPUT:")
    print("published: 0")
    print("decision: SCARCE_SIGNAL")
    print("STOP")
    exit()

# Join z-scores back
z_cols = [c for c in ["z_vwoim", "z_oi_flow", "z_gex"] if c in df_res.columns]
join_cols = [c for c in ["timestamp", "underlying", "expiry", "strike", "option_type"] if c in df_pub.columns and c in df_res.columns]
z_src = df_res.select(join_cols + z_cols).unique(subset=join_cols, keep="last")
df_pub = df_pub.join(z_src, on=join_cols, how="left", suffix="_z")

# STEP 2: Cluster by [underlying, expiry, strike, option_type]
cluster_cols = [c for c in ["underlying", "expiry", "strike", "option_type"] if c in df_pub.columns]
clusters = df_pub.group_by(cluster_cols).agg(
    pl.len().alias("cluster_size"),
    pl.col("confidence").max().alias("max_conf"),
    pl.col("confidence").mean().alias("mean_conf"),
).sort("max_conf", descending=True)

unique_clusters = clusters.height
largest_cluster = int(clusters["cluster_size"].max())
median_cluster = float(clusters["cluster_size"].median())

# STEP 4: duplicate_rate = 1 - (unique_clusters / published_count)
duplicate_rate = round(1.0 - (unique_clusters / published_count), 4)

# STEP 3: Top 20 winners
top20 = df_pub.sort("confidence", descending=True).head(20)

print("\n=== TOP 20 WINNERS ===")
hdr = "RK  UNDERLYING  EXPIRY      STRIKE    TYPE  CONF      SPREAD   VOLUME      Z_VWOIM   Z_OI      Z_GEX     RR"
print(hdr)
print("-" * len(hdr))

csv_rows = []
for idx in range(top20.height):
    r = top20.row(idx, named=True)
    conf = r.get("confidence", 0)
    spr = r.get("spread", 0) or 0
    vol = r.get("volume", 0) or 0
    rr = r.get("rr", r.get("risk_reward", 0)) or 0
    zv = r.get("z_vwoim", r.get("z_vwoim_z", 0)) or 0
    zo = r.get("z_oi_flow", r.get("z_oi_flow_z", 0)) or 0
    zg = r.get("z_gex", r.get("z_gex_z", 0)) or 0
    und = str(r.get("underlying", ""))
    exp = str(r.get("expiry", ""))
    stk = str(r.get("strike", ""))
    ot = str(r.get("option_type", ""))
    ts = r.get("timestamp", "")

    line = str(idx+1).ljust(4)
    line += und.ljust(12)
    line += exp.ljust(12)
    line += stk.ljust(10)
    line += ot.ljust(6)
    line += str(round(conf, 4)).ljust(10)
    line += str(round(spr, 2)).ljust(9)
    line += str(round(vol, 0)).ljust(12)
    line += str(round(zv, 4)).ljust(10)
    line += str(round(zo, 4)).ljust(10)
    line += str(round(zg, 4)).ljust(10)
    line += str(round(rr, 4))
    print(line)

    csv_rows.append({
        "timestamp": ts, "underlying": und, "expiry": exp,
        "strike": stk, "option_type": ot,
        "confidence": round(conf, 4), "spread": round(spr, 4),
        "volume": round(vol, 2), "rr": round(rr, 4),
        "z_vwoim": round(zv, 4), "z_oi_flow": round(zo, 4), "z_gex": round(zg, 4),
    })

# Cluster size distribution
print("\n=== CLUSTER SIZE DISTRIBUTION ===")
size_dist = clusters.group_by("cluster_size").len().sort("cluster_size")
for r in size_dist.iter_rows(named=True):
    print("  size=" + str(r["cluster_size"]) + "  contracts=" + str(r["len"]))

# STEP 5: Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/published_signal_sanity.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
    writer.writeheader()
    writer.writerows(csv_rows)

best_conf = round(float(df_pub["confidence"].max()), 4)

if duplicate_rate > 0.80:
    decision = "CLUSTERED_SIGNAL"
elif unique_clusters >= 10:
    decision = "REAL_BREAKOUT"
elif published_count < 10:
    decision = "SCARCE_SIGNAL"
else:
    decision = "MIXED"

print("\nOUTPUT:")
print("published: " + str(published_count))
print("unique_clusters: " + str(unique_clusters))
print("largest_cluster: " + str(largest_cluster))
print("median_cluster: " + str(median_cluster))
print("duplicate_rate: " + str(duplicate_rate))
print("best_confidence: " + str(best_conf))
print("decision: " + decision)
print("STOP")
