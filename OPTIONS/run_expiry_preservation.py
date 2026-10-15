"""PHASE O2F.1 — REAL EXPIRY PRESERVATION CHECK"""
import glob, os, polars as pl
from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from opportunities.universe import build_universe

date_str = "2026-06-19"
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed")

# STEP 1: Raw option contracts only
df_opt = df_raw.filter((pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"])))
raw_expiries = sorted(df_opt["expiry"].unique().to_list())
raw_counts = df_opt.group_by("expiry").len().sort("expiry")
print("=== STEP 1: RAW OPTION EXPIRIES ===")
for r in raw_counts.iter_rows(named=True):
    print("  " + repr(r["expiry"]) + " -> " + str(r["len"]) + " rows")

# STEP 2: Through features + research + patched universe
res = process_features(df_raw, date_str, dry_run=False)
df_feat = res["df_features"]
df_res = compute_gex_proxy(compute_regime_features(compute_vwoim(compute_oi_flow(df_feat))))
df_res = df_res.sort("timestamp")

# Build composite
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

# Run through universe per timestamp, collect all outputs
univ_dfs = []
for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    df_u = build_universe(df_ts)
    if not df_u.is_empty():
        univ_dfs.append(df_u)

df_univ = pl.concat(univ_dfs, how="vertical_relaxed") if univ_dfs else pl.DataFrame()

# Filter universe to option contracts only
df_univ_opt = df_univ.filter((pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"])))
univ_expiries = sorted(df_univ_opt["expiry"].unique().to_list())
univ_counts = df_univ_opt.group_by("expiry").len().sort("expiry")

print("\n=== STEP 2: UNIVERSE OPTION EXPIRIES ===")
for r in univ_counts.iter_rows(named=True):
    print("  " + repr(r["expiry"]) + " -> " + str(r["len"]) + " rows")

# STEP 3: Compare
raw_set = set(raw_expiries)
univ_set = set(univ_expiries)
missing = sorted(raw_set - univ_set)
new = sorted(univ_set - raw_set)
retention = len(raw_set & univ_set) / len(raw_set) * 100 if raw_set else 0

if raw_set == univ_set:
    decision = "REAL_EXPIRY_OK"
elif len(missing) > 0:
    decision = "UNIVERSE_DROPPING_REAL"
elif len(new) > 0:
    decision = "UNIVERSE_STILL_GENERATING"
else:
    decision = "UNKNOWN"

print("\nOUTPUT:")
print("raw_expiry: " + str(raw_expiries))
print("universe_expiry: " + str(univ_expiries))
print("missing_expiry: " + str(missing))
print("new_expiry: " + str(new))
print("retention_ratio: " + str(round(retention, 1)) + "%")
print("decision: " + decision)
print("STOP")
