"""
Technical Chart Analysis Signals.

Computes leading/confirming indicators from option price time series:
- RSI (Relative Strength Index)
- EMA 9/21 crossover
- VWAP (Volume-Weighted Average Price)
- Bollinger Band squeeze (%B)
- Price momentum (rate of change)
"""
import polars as pl
from loguru import logger


def compute_chart_signals(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add chart-based technical indicators to the DataFrame.
    Expects columns: timestamp, ltp, volume, bid, ask, underlying, expiry, strike, option_type.
    Returns df with additional signal columns.
    """
    if df.is_empty() or "ltp" not in df.columns:
        return df

    pk = ["underlying", "expiry", "strike", "option_type"]

    # --- RSI(14) ---
    # Measures momentum: >70 overbought, <30 oversold
    # For options, RSI divergence from the underlying signals directional pressure
    df = df.with_columns(
        (pl.col("ltp") - pl.col("ltp").shift(1).over(pk))
        .fill_null(0)
        .alias("_price_change")
    )
    df = df.with_columns([
        pl.when(pl.col("_price_change") > 0)
        .then(pl.col("_price_change"))
        .otherwise(0.0)
        .alias("_gain"),
        pl.when(pl.col("_price_change") < 0)
        .then(-pl.col("_price_change"))
        .otherwise(0.0)
        .alias("_loss"),
    ])
    df = df.with_columns([
        pl.col("_gain").rolling_mean(14).over(pk).fill_null(0).alias("_avg_gain"),
        pl.col("_loss").rolling_mean(14).over(pk).fill_null(0.001).alias("_avg_loss"),
    ])
    df = df.with_columns(
        (100.0 - 100.0 / (1.0 + pl.col("_avg_gain") / (pl.col("_avg_loss") + 1e-10)))
        .clip(0, 100)
        .alias("rsi_14")
    )

    # --- EMA 9/21, VWAP, ADX (on UNDERLYING SPOT chronologically) ---
    if "spot" in df.columns:
        # 1. Add truncated minute for exact joining
        df = df.with_columns(
            pl.from_epoch("timestamp", time_unit="ms").dt.truncate("1m").alias("_minute")
        )
        
        # 2. Extract chronological pure spot series (unique per minute)
        df_spot = df.select(["underlying", "_minute", "spot", "volume"]).sort(["underlying", "_minute"]).unique(subset=["underlying", "_minute"], keep="last")
        
        # 3. Calculate indicators on the pure time series
        spot_pk = ["underlying"]
        df_spot = df_spot.with_columns([
            pl.col("spot").ewm_mean(span=9).over(spot_pk).alias("_spot_ema_9"),
            pl.col("spot").ewm_mean(span=21).over(spot_pk).alias("_spot_ema_21"),
            
            # ADX setup
            pl.col("spot").rolling_max(15).over(spot_pk).alias("_spot_high_15"),
            pl.col("spot").rolling_min(15).over(spot_pk).alias("_spot_low_15"),
            (pl.col("spot") - pl.col("spot").shift(15)).abs().over(spot_pk).alias("_dm_15"),
            
            # VWAP setup (if volume exists)
        ])
        
        if "volume" in df.columns:
            df_spot = df_spot.with_columns([
                (pl.col("spot") * pl.col("volume")).cum_sum().over(spot_pk).alias("_cum_pv"),
                (pl.col("spot").pow(2) * pl.col("volume")).cum_sum().over(spot_pk).alias("_cum_pv2"),
                pl.col("volume").cum_sum().over(spot_pk).alias("_cum_vol")
            ])
        else:
            df_spot = df_spot.with_columns([pl.lit(1.0).alias("_cum_pv"), pl.lit(1.0).alias("_cum_vol")])
        
        df_spot = df_spot.with_columns([
            ((pl.col("_spot_ema_9") - pl.col("_spot_ema_21")) / (pl.col("_spot_ema_21") + 1e-8)).alias("ema_cross_pct"),
            
            # ADX calculation
            (((pl.col("_dm_15") / (pl.col("_spot_high_15") - pl.col("_spot_low_15") + 1e-8))
              .clip(0, 1) * 100)
             .ewm_mean(span=14).over(spot_pk)).alias("spot_adx_14"),
             
            # VWAP calculation
            (pl.col("_cum_pv") / (pl.col("_cum_vol") + 1e-8)).alias("vwap")
        ])
        
        if "volume" in df.columns:
            df_spot = df_spot.with_columns([
                ((pl.col("_cum_pv2") / (pl.col("_cum_vol") + 1e-8)) - pl.col("vwap").pow(2)).clip(0).sqrt().alias("vwap_std")
            ])
        else:
            df_spot = df_spot.with_columns([pl.lit(0.0).alias("vwap_std")])
        
        df_spot = df_spot.with_columns(
            ((pl.col("spot") - pl.col("vwap")) / (pl.col("vwap") + 1e-8)).alias("vwap_deviation")
        )
        
        # Initial Balance (9:15 to 10:15 IST)
        # _minute is in UTC, so shift by +5h30m to get IST time for market hour checks
        df_spot = df_spot.with_columns(
            (pl.col("_minute") + pl.duration(hours=5, minutes=30)).alias("_minute_ist")
        )
        df_spot = df_spot.with_columns([
            pl.col("_minute_ist").dt.hour().alias("_hour"),
            pl.col("_minute_ist").dt.minute().alias("_min")
        ])
        df_spot = df_spot.with_columns(
            pl.when(((pl.col("_hour") == 9) & (pl.col("_min") >= 15)) | ((pl.col("_hour") == 10) & (pl.col("_min") <= 15)))
            .then(pl.col("spot"))
            .otherwise(None)
            .alias("_ib_spot")
        )
        # We want the max/min of the IB period. For real-time, this naturally forms and then locks.
        # However, over() without cumulative just gives the global max for the day. That's fine since _ib_spot is null outside the window.
        df_spot = df_spot.with_columns([
            pl.col("_ib_spot").max().over("underlying").alias("ib_high"),
            pl.col("_ib_spot").min().over("underlying").alias("ib_low")
        ])
        
        # Keep only the target indicators to join back
        df_spot_inds = df_spot.select(["underlying", "_minute", "ema_cross_pct", "spot_adx_14", "vwap", "vwap_deviation", "vwap_std", "ib_high", "ib_low"])
        
        # 4. Join back to main dataframe
        df = df.join(df_spot_inds, on=["underlying", "_minute"], how="left")
    else:
        # Fallback to option-level EMA if spot is missing
        df = df.with_columns([
            pl.col("ltp").ewm_mean(span=9).over(pk).alias("ema_9"),
            pl.col("ltp").ewm_mean(span=21).over(pk).alias("ema_21"),
        ])
        df = df.with_columns(
            ((pl.col("ema_9") - pl.col("ema_21")) / (pl.col("ema_21") + 1e-8))
            .alias("ema_cross_pct")
        )
        df = df.drop(["ema_9", "ema_21"])

    # --- Bollinger Bands %B ---
    # %B near 0 = at lower band (oversold), near 1 = at upper band (overbought)
    # Squeeze (bandwidth narrowing) = breakout imminent
    df = df.with_columns([
        pl.col("ltp").rolling_mean(20).over(pk).fill_null(pl.col("ltp")).alias("_bb_mid"),
        pl.col("ltp").rolling_std(20).over(pk).fill_null(0).alias("_bb_std"),
    ])
    df = df.with_columns([
        (pl.col("_bb_mid") + 2 * pl.col("_bb_std")).alias("_bb_upper"),
        (pl.col("_bb_mid") - 2 * pl.col("_bb_std")).alias("_bb_lower"),
    ])
    df = df.with_columns(
        ((pl.col("ltp") - pl.col("_bb_lower"))
         / (pl.col("_bb_upper") - pl.col("_bb_lower") + 1e-8))
        .clip(0, 1)
        .alias("bb_pct_b")
    )
    # Bandwidth (squeeze detection): narrow = breakout coming
    df = df.with_columns(
        ((pl.col("_bb_upper") - pl.col("_bb_lower"))
         / (pl.col("_bb_mid") + 1e-8))
        .alias("bb_bandwidth")
    )

    # --- Price Momentum (5-bar ROC) ---
    df = df.with_columns(
        ((pl.col("ltp") - pl.col("ltp").shift(5).over(pk))
         / (pl.col("ltp").shift(5).over(pk) + 1e-8))
        .fill_null(0)
        .alias("momentum_5")
    )

    # Cleanup internal columns
    drop_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(drop_cols)

    return df
