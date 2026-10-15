"""PHASE O2H — EXECUTABLE WINNER EXTRACTION"""
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

# Full pipeline
all_cands = []
for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)
df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()

# Filter published
df_pub = df_out.filter(pl.col("confidence") >= 0.75)
published_total = df_pub.height

# Join z-scores
z_cols = [c for c in ["z_vwoim", "z_oi_flow", "z_gex"] if c in df_res.columns]
join_cols = [c for c in ["timestamp", "underlying", "expiry", "strike", "option_type"] if c in df_pub.columns and c in df_res.columns]
z_src = df_res.select(join_cols + z_cols).unique(subset=join_cols, keep="last")
df_pub = df_pub.join(z_src, on=join_cols, how="left", suffix="_z")

# STEP 1: Cluster and collapse — keep highest confidence per contract
cluster_cols = ["underlying", "expiry", "strike", "option_type"]

# Count repetitions per cluster
repeat_counts = df_pub.group_by(cluster_cols).agg(pl.len().alias("times_repeated"))

# Keep best row per cluster (highest confidence)
df_best = df_pub.sort("confidence", descending=True).unique(subset=cluster_cols, keep="first")

# Join repeat counts
df_best = df_best.join(repeat_counts, on=cluster_cols, how="left")

unique_contracts = df_best.height

# STEP 2: Execution quality scoring
# Compute ranks for liquidity, spread, rr
if "volume" in df_best.columns:
    df_best = df_best.with_columns(
        pl.col("volume").rank("ordinal", descending=True).alias("vol_rank_raw")
    )
    max_vol_rank = df_best["vol_rank_raw"].max()
    df_best = df_best.with_columns(
        (1.0 - (pl.col("vol_rank_raw") - 1) / max(max_vol_rank, 1)).alias("liquidity_rank")
    )
else:
    df_best = df_best.with_columns(pl.lit(0.5).alias("liquidity_rank"))

if "spread" in df_best.columns:
    df_best = df_best.with_columns(
        pl.col("spread").rank("ordinal", descending=False).alias("spr_rank_raw")
    )
    max_spr_rank = df_best["spr_rank_raw"].max()
    df_best = df_best.with_columns(
        (1.0 - (pl.col("spr_rank_raw") - 1) / max(max_spr_rank, 1)).alias("spread_rank")
    )
else:
    df_best = df_best.with_columns(pl.lit(0.5).alias("spread_rank"))

# RR rank (rr may be 0, use 0.5 fallback)
if "rr" in df_best.columns and df_best["rr"].max() > 0:
    df_best = df_best.with_columns(
        pl.col("rr").rank("ordinal", descending=True).alias("rr_rank_raw")
    )
    max_rr_rank = df_best["rr_rank_raw"].max()
    df_best = df_best.with_columns(
        (1.0 - (pl.col("rr_rank_raw") - 1) / max(max_rr_rank, 1)).alias("rr_rank")
    )
else:
    df_best = df_best.with_columns(pl.lit(0.5).alias("rr_rank"))

df_best = df_best.with_columns(
    (pl.col("confidence") * pl.col("liquidity_rank") * pl.col("spread_rank") * pl.col("rr_rank")).alias("execution_score")
)

# Execution filter for reporting (do not modify pipeline)
df_exec = df_best.filter(
    (pl.col("spread") <= 1.0) | (pl.col("spread").is_null())
).filter(
    (pl.col("volume") >= 5000) | (pl.col("volume").is_null())
) if "spread" in df_best.columns and "volume" in df_best.columns else df_best

executable_contracts = df_exec.height

# STEP 3: Top 20 executable winners
top20 = df_exec.sort("execution_score", descending=True).head(20)

print("=== TOP 20 EXECUTABLE WINNERS ===")
hdr = "RK  UNDERLYING  EXPIRY      STRIKE    TYPE  CONF      SPREAD   VOLUME      Z_VWOIM   Z_OI      Z_GEX     REPS  EXEC_SCORE"
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
    reps = r.get("times_repeated", 1)
    escore = r.get("execution_score", 0)
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
    line += str(reps).ljust(6)
    line += str(round(escore, 4))
    print(line)

    csv_rows.append({
        "timestamp": ts, "underlying": und, "expiry": exp,
        "strike": stk, "option_type": ot,
        "confidence": round(conf, 4), "spread": round(spr, 4),
        "volume": round(vol, 2), "rr": round(rr, 4),
        "z_vwoim": round(zv, 4), "z_oi_flow": round(zo, 4), "z_gex": round(zg, 4),
        "times_repeated": reps, "execution_score": round(escore, 4),
    })

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/executable_trade_ideas.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
    writer.writeheader()
    writer.writerows(csv_rows)

# STEP 4: Summary
best_exec = round(float(df_exec["execution_score"].max()), 4) if executable_contracts > 0 else 0
best_conf = round(float(df_exec["confidence"].max()), 4) if executable_contracts > 0 else 0
best_reps = int(df_exec.sort("execution_score", descending=True)["times_repeated"][0]) if executable_contracts > 0 else 0

if executable_contracts == 0:
    decision = "NO_EXECUTION"
elif executable_contracts <= 5:
    decision = "SELECTIVE_EXECUTION"
else:
    decision = "EXECUTION_READY"

print("\nOUTPUT:")
print("published_total: " + str(published_total))
print("unique_contracts: " + str(unique_contracts))
print("executable_contracts: " + str(executable_contracts))
print("best_confidence: " + str(best_conf))
print("best_repeat_count: " + str(best_reps))
print("decision: " + decision)
print("STOP")
