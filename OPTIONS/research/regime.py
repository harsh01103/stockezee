import polars as pl

def compute_regime_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Computes rolling regime features.
    volatility_regime: Rolling std dev of returns
    volume_regime: Ratio of recent volume to long-term volume
    trend_regime: Moving average crossover or momentum
    compression_score: Ratio of volatility to recent min volatility
    """
    if df.is_empty():
        return df
        
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    # Calculate returns for volatility
    df = df.with_columns([
        (pl.col("ltp") / pl.col("ltp").shift(1) - 1).over(pk).fill_null(0).alias("returns")
    ])
    
    # Using larger rolling windows (FIX #5: 20/60 instead of 5/20) 
    # to prevent rapid regime flipping. 60 bars on 1m data = 1 hour.
    df = df.with_columns([
        # Volatility Regime (60-bar rolling std for stability)
        pl.col("returns").rolling_std(window_size=60).over(pk).fill_null(0).alias("vol_60"),
        
        # Volume Regime (short term vs long term)
        pl.col("volume").rolling_mean(window_size=20).over(pk).fill_null(1).alias("vol_short"),
        pl.col("volume").rolling_mean(window_size=60).over(pk).fill_null(1).alias("vol_long"),
        
        # Trend Regime (price relative to 60-period MA)
        pl.col("ltp").rolling_mean(window_size=60).over(pk).fill_null(pl.col("ltp")).alias("ma_60")
    ])
    
    df = df.with_columns([
        # Classification or continuous scores
        pl.col("vol_60").alias("volatility_regime"),
        (pl.col("vol_short") / pl.col("vol_long")).fill_nan(1.0).alias("volume_regime"),
        ((pl.col("ltp") / pl.col("ma_60")) - 1).fill_nan(0.0).alias("trend_regime")
    ])
    
    # Compression score (Current Volatility / Min Volatility over 60 periods)
    df = df.with_columns([
        pl.col("vol_60").rolling_min(window_size=60).over(pk).fill_null(0.0001).alias("min_vol_60")
    ])
    
    # Add epsilon to prevent division by zero
    epsilon = 1e-8
    df = df.with_columns([
        (pl.col("vol_60") / (pl.col("min_vol_60") + epsilon)).clip(0.0, 5.0).alias("compression_score")
    ])
    
    # Calculate Regime Confidence (0-100)
    # Since the strategy is momentum-based, we want high confidence when:
    # 1. Trend is established (trend_regime > 0.002) and Volume is supporting (> 1.1)
    # 2. Or, volatility is expanding rapidly from compression (compression_score > 1.5)
    # Otherwise, it's Range/Whipsaw and confidence should be < 70
    df = df.with_columns([
        pl.when((pl.col("trend_regime").abs() > 0.002) & (pl.col("volume_regime") > 1.1))
        .then(pl.lit(80) + (pl.col("volume_regime") - 1.0) * 10)
        .when(pl.col("compression_score") > 1.5)
        .then(pl.lit(70) + (pl.col("compression_score") - 1.0) * 5)
        .otherwise(pl.lit(40))
        .clip(0, 100)
        .alias("regime_confidence")
    ])
    
    # Cleanup temp columns
    df = df.drop(["returns", "vol_60", "vol_short", "vol_long", "ma_60", "min_vol_60"])
    
    return df
