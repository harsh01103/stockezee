"""PHASE O2G — PUBLISHED SIGNAL SANITY"""
import glob, os, polars as pl
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

# Run full pipeline
all_cands = []
for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)

df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()

# Filter published only
df_pub = df_out.filter(pl.col("confidence") >= 0.75)
published_count = df_pub.height

print("=== PUBLISHED CANDIDATES ===")
print("Total published: " + str(published_count))

if published_count == 0:
    print("decision: SCARCE_SIGNAL")
    print("STOP")
    exit()

# Unique dimensions
unique_ts = df_pub["timestamp"].n_unique()
unique_underlying = df_pub["underlying"].unique().to_list()
unique_expiry = df_pub["expiry"].unique().to_list()
unique_strikes = df_pub["strike"].n_unique() if "strike" in df_pub.columns else 0
unique_types = df_pub["option_type"].unique().to_list() if "option_type" in df_pub.columns else []

print("Unique timestamps: " + str(unique_ts))
print("Unique underlyings: " + str(unique_underlying))
print("Unique expiries: " + str(unique_expiry))
print("Unique strikes: " + str(unique_strikes))
print("Unique option_types: " + str(unique_types))

# Cluster by [underlying, expiry, strike, option_type]
cluster_cols = [c for c in ["underlying", "expiry", "strike", "option_type"] if c in df_pub.columns]
clusters = df_pub.group_by(cluster_cols).agg(
    pl.len().alias("cluster_size"),
    pl.col("confidence").max().alias("max_conf"),
    pl.col("confidence").mean().alias("mean_conf"),
)
clusters = clusters.sort("max_conf", descending=True)

unique_clusters = clusters.height
largest_cluster = int(clusters["cluster_size"].max())
median_cluster = float(clusters["cluster_size"].median())

# Duplicate rate: rows that share an identical contract across timestamps
# If a contract appears N times, N-1 are "duplicates" (same strike/expiry just different timestamps)
unique_contracts = df_pub.unique(subset=cluster_cols).height
duplicate_rows = published_count - unique_contracts
duplicate_rate = round(duplicate_rows / published_count * 100, 1) if published_count > 0 else 0

print()
print("=== CLUSTER ANALYSIS ===")
print("Unique clusters (contract identities): " + str(unique_clusters))
print("Largest cluster (most repeated contract): " + str(largest_cluster))
print("Median cluster size: " + str(median_cluster))
print("Unique contracts: " + str(unique_contracts))
print("Duplicate rows (same contract, different ts): " + str(duplicate_rows))
print("Duplicate rate: " + str(duplicate_rate) + "%")

# Cluster size distribution
print()
print("=== CLUSTER SIZE DISTRIBUTION ===")
size_dist = clusters.group_by("cluster_size").len().sort("cluster_size")
for r in size_dist.iter_rows(named=True):
    print("  size=" + str(r["cluster_size"]) + "  clusters=" + str(r["len"]))

# Top 20 winners
print()
print("=== TOP 20 WINNERS ===")
top20 = df_pub.sort("confidence", descending=True).head(20)

header = "RANK  UNDERLYING  EXPIRY      STRIKE    TYPE  CONFIDENCE  SPREAD     VOLUME     RR"
print(header)
print("-" * len(header))

for idx in range(top20.height):
    r = top20.row(idx, named=True)
    conf = r.get("confidence", 0)
    spr = r.get("spread", 0) or 0
    vol = r.get("volume", 0) or 0
    rr = r.get("rr", r.get("risk_reward", 0)) or 0
    ts = r.get("timestamp", "")
    und = str(r.get("underlying", ""))
    exp = str(r.get("expiry", ""))
    stk = str(r.get("strike", ""))
    ot = str(r.get("option_type", ""))
    
    line = str(idx+1).ljust(6)
    line += und.ljust(12)
    line += exp.ljust(12)
    line += stk.ljust(10)
    line += ot.ljust(6)
    line += str(round(conf, 4)).ljust(12)
    line += str(round(spr, 2)).ljust(11)
    line += str(round(vol, 0)).ljust(11)
    line += str(round(rr, 4))
    print(line)

# Decision
if duplicate_rate > 80:
    decision = "CLUSTERED_SIGNAL"
elif unique_clusters >= 10:
    decision = "REAL_BREAKOUT"
elif published_count < 10:
    decision = "SCARCE_SIGNAL"
else:
    decision = "MIXED"

print()
print("OUTPUT:")
print("published: " + str(published_count))
print("unique_clusters: " + str(unique_clusters))
print("largest_cluster: " + str(largest_cluster))
print("duplicate_rate: " + str(duplicate_rate) + "%")
print("decision: " + decision)
print("STOP")
