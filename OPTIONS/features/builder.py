# pyrefly: ignore [missing-import]
import polars as pl
from pathlib import Path
# pyrefly: ignore [missing-import]
from loguru import logger
from datetime import datetime
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="Sortedness of columns cannot be checked.*")

from features.tod_normalizer import normalize_tod
from features.strike_matrix import build_strike_matrix

def load_raw_data(date_str: str) -> pl.DataFrame:
    raw_dir = Path(f"data/raw/{date_str}")
    if not raw_dir.exists():
        logger.warning(f"No raw data found for {date_str}")
        return pl.DataFrame()
        
    files = list(raw_dir.glob("*.parquet"))
    if not files:
        return pl.DataFrame()
        
    dfs = []
    for f in files:
        df = pl.read_parquet(f)
        df = df.with_columns(pl.lit(f.name).alias("source_file"))
        dfs.append(df)
        
    return pl.concat(dfs, how="vertical_relaxed") if dfs else pl.DataFrame()

def build_features(date_str: str, dry_run: bool = False) -> dict:
    start_time = datetime.now()
    
    df_raw = load_raw_data(date_str)
    return process_features(df_raw, date_str, dry_run, start_time)

def process_features(df_raw: pl.DataFrame, date_str: str, dry_run: bool = False, start_time: datetime = None) -> dict:
    if start_time is None:
        start_time = datetime.now()
        
    if df_raw.is_empty():
        return {
            "rows_loaded": 0, "rows_output": 0, 
            "duplicates_removed": 0, "build_time": 0,
            "df_features": pl.DataFrame()
        }
        
    if "source_file" not in df_raw.columns:
        df_raw = df_raw.with_columns(pl.lit("live").alias("source_file"))
        
    rows_loaded = df_raw.height
    
    # 1. Deduplicate
    pk = ["timestamp", "underlying", "expiry", "strike", "option_type"]
    df_dedup = df_raw.unique(subset=pk, keep="last")
    duplicates_removed = rows_loaded - df_dedup.height
    
    # Sort
    df_dedup = df_dedup.sort(["underlying", "expiry", "strike", "option_type", "timestamp"])
    
    df = df_dedup.with_columns([
        (pl.col("ask") - pl.col("bid")).alias("spread"),
        ((pl.col("ask") + pl.col("bid")) / 2).alias("mid_price"),
        pl.from_epoch("timestamp", time_unit="ms").dt.strftime("%H:%M").alias("session_slot")
    ])
    

    df = df.sort(["underlying", "expiry", "strike", "option_type", "timestamp"])
    
    # Calculate delta_oi and delta_volume
    df = df.with_columns([
        (pl.col("oi") - pl.col("oi").shift(1)).over(["underlying", "expiry", "strike", "option_type"]).fill_null(0).alias("delta_oi"),
        (pl.col("volume") - pl.col("volume").shift(1)).over(["underlying", "expiry", "strike", "option_type"]).fill_null(0).alias("delta_volume")
    ])
    # 3. Merge spot price from index ticks
    df_index = df.filter(pl.col("strike") == 0.0)
    if df_index.height > 0:
        # Fix mislabeled BankNifty index ticks in historical data (both had underlying="NIFTY")
        df_index = df_index.with_columns(
            pl.when(pl.col("ltp") > 40000).then(pl.lit("BANKNIFTY"))
            .otherwise(pl.lit("NIFTY"))
            .alias("underlying")
        )
        df_index = df_index.select(["timestamp", "underlying", pl.col("ltp").alias("true_spot")])
        df_index = df_index.sort("timestamp").set_sorted("timestamp")
        
        df_options = df.filter(pl.col("strike") > 0.0).sort("timestamp").set_sorted("timestamp")
        
        df_joined = df_options.join_asof(
            df_index,
            on="timestamp",
            by="underlying",
            strategy="backward"
        )
        
        df = df_joined.with_columns(
            pl.col("true_spot").fill_null(0.0).alias("spot")
        ).drop("true_spot")
    else:
        df = df.filter(pl.col("strike") > 0.0)
    
    # 4. Generate Granularities
    df = df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("datetime"))
    granularities = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m"
    }
    
    rows_output = 0
    final_dfs = {}
    
    for label, interval in granularities.items():
        # group by truncated time, and take the last values
        df_resampled = df.group_by_dynamic(
            "datetime", every=interval, group_by=["underlying", "expiry", "strike", "option_type"]
        ).agg(
            pl.col("timestamp").last(),
            pl.col("spot").last(),
            pl.col("ltp").last(),
            pl.col("bid").last(),
            pl.col("ask").last(),
            pl.col("spread").last(),
            pl.col("volume").last(),
            pl.col("oi").last(),
            pl.col("delta_oi").sum(),
            pl.col("delta_volume").sum(),
            pl.col("mid_price").last(),
            pl.col("session_slot").last(),
            pl.col("source_file").last()
        )
        
        # Now apply strike matrix and normalizer on the resampled bars
        df_resampled = build_strike_matrix(df_resampled)
        df_resampled = normalize_tod(df_resampled)
        
        # Format back schema
        df_resampled = df_resampled.drop("datetime")
        
        # Ensure schema order and drop extra
        from features.schema import FEATURE_SCHEMA
        for col in FEATURE_SCHEMA.keys():
            if col not in df_resampled.columns:
                df_resampled = df_resampled.with_columns(pl.lit(None).alias(col))
                
        df_resampled = df_resampled.select(list(FEATURE_SCHEMA.keys()))
        
        final_dfs[label] = df_resampled
        rows_output += df_resampled.height
        
        if not dry_run and df_resampled.height > 0:
            out_dir = Path(f"data/features/{date_str}/{label}")
            out_dir.mkdir(parents=True, exist_ok=True)
            df_resampled.write_parquet(out_dir / f"features_{date_str}.parquet")

    build_time = (datetime.now() - start_time).total_seconds()
    
    return {
        "rows_loaded": rows_loaded,
        "rows_output": rows_output,
        "duplicates_removed": duplicates_removed,
        "build_time": build_time,
        "df_features": final_dfs.get("1m", pl.DataFrame()) # Return 1m for quality checks
    }
