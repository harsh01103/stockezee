import glob, polars as pl, os
from datetime import datetime
import logging

os.environ["MOCK_AUTH"] = "true"

from features.builder import process_features
from research.chart_signals import compute_chart_signals
from research.regime import compute_regime_features
from runner import run_momentum_engine, run_mean_reversion_engine, is_executable

logging.basicConfig(level=logging.ERROR)

# Monkey-patch httpx.get for the ledger request to return empty trades instantly
import httpx
original_get = httpx.get
def mock_get(url, *args, **kwargs):
    if "api/ledger" in url:
        class MockResp:
            status_code = 200
            def json(self): return {"trades": []}
        return MockResp()
    return original_get(url, *args, **kwargs)
httpx.get = mock_get

files = sorted(glob.glob('data/raw/2026-07-24/*.parquet'))
if files:
    dfs = [pl.read_parquet(f).with_columns(pl.lit(f).alias('source_file')) for f in files]
    df = pl.concat(dfs, how='diagonal')
    feat_dict = process_features(df, '2026-07-24')
    df_feat = feat_dict['df_features']
    df_feat = compute_chart_signals(df_feat)
    df_feat = compute_regime_features(df_feat)
    
    # Filter 9:30 to 9:45 data for candidates
    df_feat = df_feat.with_columns(
        (pl.from_epoch(pl.col('timestamp').cast(pl.Int64), time_unit='ms') + pl.duration(hours=5, minutes=30)).alias('datetime_ist')
    )
    
    df_window = df_feat.filter(
        (pl.col('datetime_ist').dt.hour() == 9) & 
        (pl.col('datetime_ist').dt.minute() >= 30) & 
        (pl.col('datetime_ist').dt.minute() < 45)
    )
    
    unique_ts = sorted(df_window['timestamp'].unique().to_list())
    print(f'Simulating over {len(unique_ts)} timestamps between 9:30 and 9:45...')
    
    candidates_found = []
    
    for ts in unique_ts:
        df_until_now = df_feat.filter(pl.col('timestamp') <= ts)
        df_mom = run_momentum_engine(df_until_now, ts, date_str='2026-07-24', dry_run=True)
        if df_mom is not None and not df_mom.is_empty():
            for row in df_mom.to_dicts():
                import runner
                runner.all_signals = [] 
                ok, reason = is_executable(row)
                
                if not ok and 'alpha_direction_conflict' in reason:
                    print(f'BLOCKED BY NEW ALPHA GATE: {row["strike"]} {row["option_type"]} - {reason}')
                
                if not ok and 'time_of_day_early_block' in reason:
                    ok = True
                    reason = 'OK (time block bypassed)'
                    
                if ok:
                    candidates_found.append(row)
    
    print(f'\nTotal VALID trades that would have fired between 9:30 and 9:45: {len(candidates_found)}')
    for c in candidates_found:
        alpha = c.get("composite_alpha_score", 0)
        conf = c.get("confidence", 0)
        print(f'Trade: {c["underlying"]} {c["strike"]} {c["option_type"]} {c["action"]} | Alpha: {alpha:.2f} | Conf: {conf:.2f}')
