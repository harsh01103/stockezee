import glob, logging, os
from datetime import datetime
import polars as pl

# Disable auth network check for dry-run
os.environ["MOCK_AUTH"] = "true"

from features.builder import process_features
from research.chart_signals import compute_chart_signals
from research.regime import compute_regime_features
from runner import run_momentum_engine, run_mean_reversion_engine, is_executable, build_trade_idea

logging.basicConfig(level=logging.ERROR)

files = sorted(glob.glob('data/raw/2026-07-23/*.parquet'))[:50]
print(f'Testing fast dry-run on {len(files)} parquet files...')

dfs = [pl.read_parquet(f).with_columns(pl.lit(f).alias('source_file')) for f in files]
df_raw = pl.concat(dfs, how='diagonal')

feat_dict = process_features(df_raw, '2026-07-23')
df_feat = feat_dict['df_features']
df_feat = compute_chart_signals(df_feat)
df_feat = compute_regime_features(df_feat)

print('Feature pipeline output shape:', df_feat.shape)
print('IB High sample:', [round(x, 2) for x in df_feat['ib_high'].drop_nulls().unique().to_list()[:3]])
print('IB Low sample:', [round(x, 2) for x in df_feat['ib_low'].drop_nulls().unique().to_list()[:3]])

# Test momentum engine
t0 = df_feat['timestamp'].max()
df_mom = run_momentum_engine(df_feat, t0, date_str='2026-07-23', dry_run=True)
print('Momentum engine candidates:', df_mom.shape if df_mom is not None else 'None')

# Test mean reversion engine
df_mr = run_mean_reversion_engine(df_feat, t0, latest_spot_direction='BULLISH')
print('Mean Reversion engine candidates:', df_mr.shape if df_mr is not None else 'None')

# Test is_executable and build_trade_idea on top candidate if exists
test_df = df_mom if (df_mom is not None and not df_mom.is_empty()) else df_mr
if test_df is not None and not test_df.is_empty():
    candidate = test_df.to_dicts()[0]
    ok, reason = is_executable(candidate)
    strike = candidate.get("strike")
    op_type = candidate.get("option_type")
    print(f'Execution check on candidate ({strike}_{op_type}): OK={ok}, Reason={reason}')
    idea = build_trade_idea(candidate, datetime.now(), test_df, df_raw)
    print('Trade idea generated successfully:')
    print('  Strategy:', idea.get('strategy'))
    print('  Features count:', len(idea.get('_features', {})))
    print('  Size multiplier:', idea.get('size_multiplier'))

print('\nEND-TO-END FAST DRY RUN PASSED WITH 0 ERRORS!')
