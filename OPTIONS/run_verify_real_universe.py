"""PHASE O2F — VERIFY REAL-ONLY UNIVERSE + LIVE INFERENCE"""
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

# Verify: pre-universe expiries
pre_expiries = df_res["expiry"].unique().sort().to_list()
print("Pre-universe expiries: " + str(pre_expiries))

# Run through universe per timestamp
rows_before_total = 0
rows_after_total = 0
all_cands = []

for ts in sorted(df_res["timestamp"].unique().to_list()):
    df_ts = df_res.filter(pl.col("timestamp") == ts)
    rows_before_total += df_ts.height
    
    df_univ = build_universe(df_ts)
    rows_after_total += df_univ.height
    
    if df_univ.is_empty():
        continue
    
    df_opp = calculate_confidence(rank_opportunities(score_opportunities(df_univ)))
    if not df_opp.is_empty() and "confidence" in df_opp.columns:
        all_cands.append(df_opp)

df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()

# Post-universe expiries
if not df_out.is_empty():
    post_expiries = df_out["expiry"].unique().sort().to_list()
    peak_conf = float(df_out["confidence"].max())
    published = df_out.filter(pl.col("confidence") > 0.75).height
    cand_count = df_out.height
else:
    post_expiries = []
    peak_conf = 0.0
    published = 0
    cand_count = 0

generated_rows = max(0, rows_after_total - rows_before_total)
expiry_preserved = set(str(e) for e in post_expiries).issubset(set(str(e) for e in pre_expiries)) if post_expiries else True

print("Post-universe expiries: " + str(post_expiries))
print("Rows before universe: " + str(rows_before_total))
print("Rows after universe: " + str(rows_after_total))
print("Generated rows: " + str(generated_rows))
print("Expiry preserved: " + str(expiry_preserved))
print("Candidates: " + str(cand_count))
print("Peak confidence: " + str(round(peak_conf, 4)))
print("Published: " + str(published))

if generated_rows > 0:
    decision = "FAIL"
elif expiry_preserved:
    decision = "REAL_ONLY"
else:
    decision = "FAIL"

print()
print("OUTPUT:")
print("rows_before: " + str(rows_before_total))
print("rows_after: " + str(rows_after_total))
print("generated_rows: " + str(generated_rows))
print("peak_confidence: " + str(round(peak_conf, 4)))
print("published: " + str(published))
print("decision: " + decision)
print("STOP")
