# pyrefly: ignore [missing-import]
import polars as pl

def compute_oi_flow(df: pl.DataFrame) -> pl.DataFrame:
    """
    Computes OI flow dynamics.
    Requires: volume, oi, delta_oi
    """
    if df.is_empty():
        return df
        
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    # Ensure dataframe is sorted by time for accurate cumulative functions
    df = df.sort(["underlying", "expiry", "strike", "option_type", "timestamp"])

    df = df.with_columns([
        pl.col("delta_oi").cum_sum().over(pk).alias("cum_delta_oi"),
        (pl.col("volume") * pl.col("delta_oi")).alias("volume_weighted_oi")
    ])
    
    # Velocity is rate of change of OI
    df = df.with_columns([
        # oi_velocity = delta_oi / 1 (since it's per bar, we can just use delta_oi or smoothed delta_oi)
        # Let's use a 3-bar moving average of delta_oi
        pl.col("delta_oi").rolling_mean(window_size=3).over(pk).fill_null(0).alias("oi_velocity")
    ])
    
    # Acceleration is rate of change of velocity
    df = df.with_columns([
        (pl.col("oi_velocity") - pl.col("oi_velocity").shift(1)).over(pk).fill_null(0).alias("oi_acceleration")
    ])
    
    # oi_flow_score could be a composite
    df = df.with_columns([
        ((pl.col("oi_velocity") * 0.5) + (pl.col("oi_acceleration") * 0.5)).alias("oi_flow_score")
    ])
    
    # ── INSTITUTIONAL: Put-Call Ratio (PCR) and dPCR/dt ──────────────
    # PCR = Total Put OI / Total Call OI per underlying per timestamp.
    # dPCR/dt = 5-bar rate of change of PCR.
    # A sharply rising dPCR/dt confirms aggressive put writing (bullish floor).
    # A sharply falling dPCR/dt confirms aggressive call writing (bearish ceiling).
    if "option_type" in df.columns and "oi" in df.columns:
        ts_pk = ["timestamp", "underlying"]
        
        # Sum OI by option type per timestamp per underlying
        put_oi = (
            df.filter(pl.col("option_type") == "PE")
            .group_by(ts_pk)
            .agg(pl.col("oi").sum().alias("_total_put_oi"))
        )
        call_oi = (
            df.filter(pl.col("option_type") == "CE")
            .group_by(ts_pk)
            .agg(pl.col("oi").sum().alias("_total_call_oi"))
        )
        
        pcr_df = put_oi.join(call_oi, on=ts_pk, how="full", coalesce=True)
        pcr_df = pcr_df.with_columns([
            pl.col("_total_put_oi").fill_null(0),
            pl.col("_total_call_oi").fill_null(0),
        ])
        pcr_df = pcr_df.with_columns(
            (pl.col("_total_put_oi") / (pl.col("_total_call_oi") + 1e-8)).alias("pcr")
        )
        
        # dPCR/dt: 5-bar rate of change of PCR (per underlying)
        pcr_df = pcr_df.sort(["underlying", "timestamp"])
        pcr_df = pcr_df.with_columns(
            ((pl.col("pcr") - pl.col("pcr").shift(5).over("underlying"))
             / (pl.col("pcr").shift(5).over("underlying") + 1e-8))
            .fill_null(0).alias("dpcr_dt")
        )
        
        pcr_df = pcr_df.select(ts_pk + ["pcr", "dpcr_dt"])
        
        # Join back to the main df so every row gets its underlying's PCR context
        df = df.join(pcr_df, on=ts_pk, how="left")
    
    # ── INSTITUTIONAL: Per-Strike 5-bar COI for Short Covering Detection ──
    # A rapid negative COI on OTM Call strikes = call writers panicking = forced buying
    if "delta_oi" in df.columns:
        df = df.with_columns(
            pl.col("delta_oi").rolling_sum(window_size=5).over(pk).fill_null(0).alias("coi_5bar")
        )
    
    return df
