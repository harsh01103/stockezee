"""PHASE O2C — EXPIRY REALITY AUDIT"""
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

# STEP 1: Raw expiries
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file")) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed")
raw_expiries = df_raw["expiry"].unique().sort().to_list()
raw_counts = df_raw.group_by("expiry").agg(pl.count().alias("n")).sort("expiry")
print("=== STEP 1: RAW EXPIRIES ===")
print(f"Unique: {len(raw_expiries)}")
for r in raw_counts.iter_rows(named=True):
    print(f"  {r['expiry']}  rows={r['n']}")

# STEP 2: Feature expiries
res = process_features(df_raw, date_str, dry_run=False)
df_feat = res["df_features"]
feat_expiries = df_feat["expiry"].unique().sort().to_list()
feat_counts = df_feat.group_by("expiry").agg(pl.count().alias("n")).sort("expiry")
print("\n=== STEP 2: FEATURE EXPIRIES ===")
print(f"Unique: {len(feat_expiries)}")
for r in feat_counts.iter_rows(named=True):
    print(f"  {r['expiry']}  rows={r['n']}")

# Trace through research stages
df_r1 = compute_oi_flow(df_feat)
print(f"\nAfter oi_flow: {df_r1['expiry'].n_unique()} expiries")
df_r2 = compute_vwoim(df_r1)
print(f"After vwoim: {df_r2['expiry'].n_unique()} expiries")
df_r3 = compute_regime_features(df_r2)
print(f"After regime: {df_r3['expiry'].n_unique()} expiries")
df_r4 = compute_gex_proxy(df_r3)
print(f"After gex: {df_r4['expiry'].n_unique()} expiries")

# Build composite
df_sig = df_r4.sort("timestamp")
pk = ["underlying", "expiry", "strike", "option_type"]
def zscore(col):
    return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
           (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
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

# Trace through universe/scorer/ranker/confidence on last timestamp
sample_ts = sorted(df_sig["timestamp"].unique().to_list())[-1]
df_ts = df_sig.filter(pl.col("timestamp") == sample_ts)

pre_exp = df_ts["expiry"].unique().sort().to_list()
print(f"\nPre-universe (last ts): {len(pre_exp)} expiries: {pre_exp}")

df_univ = build_universe(df_ts)
univ_exp = df_univ["expiry"].unique().sort().to_list()
print(f"After universe: {len(univ_exp)} expiries: {univ_exp}")

df_scored = score_opportunities(df_univ)
scored_exp = df_scored["expiry"].unique().sort().to_list()
print(f"After scorer: {len(scored_exp)} expiries: {scored_exp}")

df_ranked = rank_opportunities(df_scored)
ranked_exp = df_ranked["expiry"].unique().sort().to_list()
print(f"After ranker: {len(ranked_exp)} expiries: {ranked_exp}")

df_conf = calculate_confidence(df_ranked)
conf_exp = df_conf["expiry"].unique().sort().to_list()
print(f"After confidence: {len(conf_exp)} expiries: {conf_exp}")

# STEP 3: Candidate expiries (full run)
all_cands = []
for ts in sorted(df_sig["timestamp"].unique().to_list()):
    df_t = df_sig.filter(pl.col("timestamp") == ts)
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_t))))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)
df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()
cand_expiries = df_out["expiry"].unique().sort().to_list()
cand_counts = df_out.group_by("expiry").agg(pl.count().alias("n")).sort("expiry")
print("\n=== STEP 3: CANDIDATE EXPIRIES ===")
print(f"Unique: {len(cand_expiries)}")
for r in cand_counts.iter_rows(named=True):
    print(f"  {r['expiry']}  rows={r['n']}")

# STEP 4: Compare
raw_set = set(str(e) for e in raw_expiries)
feat_set = set(str(e) for e in feat_expiries)
cand_set = set(str(e) for e in cand_expiries)

mismatch = "NONE"
rows_affected = 0
if raw_set != feat_set:
    mismatch = "features"
    diff = raw_set.symmetric_difference(feat_set)
    rows_affected = df_raw.filter(pl.col("expiry").cast(pl.Utf8).is_in(list(diff))).height
elif feat_set != cand_set:
    mismatch = "universe"
    diff = feat_set.symmetric_difference(cand_set)
    rows_affected = df_feat.filter(pl.col("expiry").cast(pl.Utf8).is_in(list(diff))).height

if raw_set == feat_set == cand_set:
    decision = "EXPIRY_OK"
elif raw_set != feat_set:
    decision = "EXPIRY_MAPPING_BUG"
else:
    decision = "OUTPUT_JOIN_BUG"

print("\nOUTPUT:")
print(f"raw_expiry: {sorted(raw_set)}")
print(f"feature_expiry: {sorted(feat_set)}")
print(f"candidate_expiry: {sorted(cand_set)}")
print(f"first_mismatch_stage: {mismatch}")
print(f"rows_affected: {rows_affected}")
print(f"decision: {decision}")
print("STOP")
