"""PHASE O2E — OPTION EXPIRY INTEGRITY CHECK"""
import glob, os, polars as pl
from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

date_str = "2026-06-19"
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed")

# STEP 1: Filter to real option contracts only
df_options = df_raw.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
)
df_index = df_raw.filter(
    (pl.col("strike") == 0) | (~pl.col("option_type").is_in(["CE", "PE"]))
)

total_raw = df_raw.height
option_rows = df_options.height
index_rows = df_index.height

opt_expiries = df_options["expiry"].unique().sort().to_list()
opt_missing = df_options.filter(pl.col("expiry") == "").height
opt_real = df_options.filter(pl.col("expiry") != "").height

idx_expiries = df_index["expiry"].unique().sort().to_list()
idx_missing = df_index.filter(pl.col("expiry") == "").height

print("=== STEP 1: RAW OPTION CONTRACTS ===")
print("total_raw: " + str(total_raw))
print("option_rows (strike>0 & CE/PE): " + str(option_rows))
print("index_rows (strike=0 or not CE/PE): " + str(index_rows))
print()
print("Option unique_expiry: " + str(opt_expiries))
print("Option missing_expiry: " + str(opt_missing))
print("Option real_expiry: " + str(opt_real))
print("Option missing_ratio: " + str(round(opt_missing/option_rows*100, 2) if option_rows > 0 else 0) + "%")
print()
print("Index unique_expiry: " + str(idx_expiries))
print("Index missing_expiry: " + str(idx_missing))

# Show expiry distribution for option rows
print()
print("=== OPTION EXPIRY DISTRIBUTION ===")
opt_exp_counts = df_options.group_by("expiry").len().sort("expiry")
for r in opt_exp_counts.iter_rows(named=True):
    print("  expiry=" + repr(r["expiry"]) + "  count=" + str(r["len"]))

# STEP 2: Trace through features and research
print()
print("=== STEP 2: FEATURES ===")
res = process_features(df_raw, date_str, dry_run=False)
df_feat = res["df_features"]

# Filter features to option contracts
df_feat_opt = df_feat.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
)
feat_opt_expiries = df_feat_opt["expiry"].unique().sort().to_list()
feat_opt_missing = df_feat_opt.filter(pl.col("expiry") == "").height

print("Feature option rows: " + str(df_feat_opt.height))
print("Feature option expiries: " + str(feat_opt_expiries))
print("Feature option missing_expiry: " + str(feat_opt_missing))

# Research
print()
print("=== STEP 2: RESEARCH ===")
df_res = compute_gex_proxy(compute_regime_features(compute_vwoim(compute_oi_flow(df_feat))))
df_res_opt = df_res.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
)
res_opt_expiries = df_res_opt["expiry"].unique().sort().to_list()
res_opt_missing = df_res_opt.filter(pl.col("expiry") == "").height

print("Research option rows: " + str(df_res_opt.height))
print("Research option expiries: " + str(res_opt_expiries))
print("Research option missing_expiry: " + str(res_opt_missing))

# STEP 3: Check what universe sees per-timestamp
print()
print("=== STEP 3: PRE-UNIVERSE INSPECTION ===")

# Build composite
pk = ["underlying", "expiry", "strike", "option_type"]
def zscore(col):
    return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
           (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
df_sig = df_res.sort("timestamp")
features = []
if "vwoim_smoothed" in df_sig.columns:
    df_sig = df_sig.with_columns(zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"))
    features.append("z_vwoim")
if "oi_flow_score" in df_sig.columns:
    df_sig = df_sig.with_columns(zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"))
    features.append("z_oi_flow")
if "gex_proxy" in df_sig.columns:
    df_sig = df_sig.with_columns(zscore("gex_proxy").fill_null(0).alias("z_gex"))
    features.append("z_gex")
df_sig = df_sig.with_columns(pl.sum_horizontal(features).alias("raw_score"))
df_sig = df_sig.with_columns(
    (pl.col("raw_score") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
)

# Check per-timestamp counts (what universe sees)
ts_counts = df_sig.group_by("timestamp").len().sort("timestamp")
print("Timestamps: " + str(ts_counts.height))
print("Min rows per ts: " + str(ts_counts["len"].min()))
print("Max rows per ts: " + str(ts_counts["len"].max()))
print("Median rows per ts: " + str(ts_counts["len"].median()))

# Universe triggers at max_c < 20 — check how many timestamps have < 20 rows
under_20 = ts_counts.filter(pl.col("len") < 20).height
over_20 = ts_counts.filter(pl.col("len") >= 20).height
print("Timestamps with < 20 rows (universe triggers): " + str(under_20))
print("Timestamps with >= 20 rows (universe skips): " + str(over_20))

# Check a timestamp with >= 20 rows if any
big_ts = ts_counts.filter(pl.col("len") >= 20)
if big_ts.height > 0:
    sample_ts = big_ts["timestamp"][0]
    df_big = df_sig.filter(pl.col("timestamp") == sample_ts)
    big_exp = df_big["expiry"].unique().sort().to_list()
    big_opt = df_big.filter((pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"])))
    print()
    print("Sample large timestamp rows: " + str(df_big.height))
    print("Expiries: " + str(big_exp))
    print("Option rows: " + str(big_opt.height))
    print("Option expiries: " + str(big_opt["expiry"].unique().sort().to_list()))

# Final decision
print()
print("OUTPUT:")
print("option_rows: " + str(option_rows))
print("option_unique_expiry: " + str(opt_expiries))
print("missing_option_expiry: " + str(opt_missing))
print("expiry_preserved: " + str(opt_missing == 0 and feat_opt_missing == 0 and res_opt_missing == 0))
print("universe_generates_rows: True (line 18-56 in universe.py)")

if opt_missing == 0 and feat_opt_missing == 0:
    decision = "UNIVERSE_ONLY_BUG"
else:
    decision = "DECODER_AND_UNIVERSE"
print("decision: " + decision)
print("STOP")
