import polars as pl
import numpy as np

def score_opportunities(df: pl.DataFrame) -> pl.DataFrame:
    """
    Backward-compatible entry point for Strategy A: Momentum Breakout Scorer.
    """
    return score_momentum_opportunities(df)


def score_momentum_opportunities(df: pl.DataFrame) -> pl.DataFrame:
    """
    Strategy A Scorer (Momentum Breakout Engine).
    Preserves 100% of the high-conviction breakout logic:
      - 35% Flow Z-Scores (s_vol_burst, s_oi_accel, s_price_vel, s_ba_press)
      - 35% Delta quality (ideal ITM momentum delta ~ 0.65)
      - 20% Chart Signals (s_ema_cross, s_vwap)
      - 10% Spread quality
    """
    if df.is_empty():
        return df
        
    if "composite_alpha_score" not in df.columns:
        df = df.with_columns(pl.lit(0.0).alias("composite_alpha_score"))
    
    # 1. Flow & Signal Quality (35%)
    FLOOR, CEIL = 8.0, 30.0
    signal_score = (pl.col("composite_alpha_score").clip(FLOOR, CEIL) - FLOOR) / (CEIL - FLOOR) * 100.0
    
    # 2. Delta Quality (35%) — Peak at |delta| = 0.65 (ITM momentum)
    if "delta" in df.columns:
        delta_quality = (1.0 - ((pl.col("delta").abs() - 0.65).abs() / 0.25)).clip(0.0, 1.0) * 100.0
    else:
        delta_quality = pl.lit(50.0)
    
    # 3. Chart Signals Quality (20%)
    if "s_ema_cross" in df.columns and "s_vwap" in df.columns:
        chart_score = ((pl.col("s_ema_cross").clip(lower_bound=0.0) + pl.col("s_vwap").clip(lower_bound=0.0)) * 10.0).clip(0.0, 100.0)
    else:
        chart_score = pl.lit(50.0)
    
    # 4. Spread Quality (10%)
    if "bid" in df.columns and "ask" in df.columns:
        mid = (pl.col("bid") + pl.col("ask")) / 2.0
        spread_pct = pl.when(mid > 0).then((pl.col("ask") - pl.col("bid")) / mid).otherwise(0.02)
        spread_quality = ((0.015 - spread_pct) / 0.01).clip(0.0, 1.0) * 100.0
    else:
        spread_quality = pl.lit(50.0)
    
    df = df.with_columns(
        (signal_score * 0.35 + delta_quality * 0.35 + chart_score * 0.20 + spread_quality * 0.10)
        .fill_null(0.0).fill_nan(0.0)
        .alias("opportunity_score")
    )
    
    if "s_ba_press" in df.columns and "s_oi_accel" in df.columns:
        flow_bonus = ((pl.col("s_ba_press").clip(lower_bound=0.0) + pl.col("s_oi_accel").clip(lower_bound=0.0)) * 2.0).clip(0, 10)
        df = df.with_columns((pl.col("opportunity_score") + flow_bonus).alias("selection_score"))
    else:
        df = df.with_columns(pl.col("opportunity_score").alias("selection_score"))
    
    df = df.with_columns([
        pl.col("opportunity_score").alias("c_signal"),
        pl.lit(0.0).alias("c_vwoim"),
        pl.lit(0.0).alias("c_oi"),
        pl.lit(0.0).alias("c_regime"),
        pl.lit(0.0).alias("c_spread"),
        pl.lit(0.0).alias("c_latency")
    ])
    return df


def score_mean_reversion_opportunities(df: pl.DataFrame) -> pl.DataFrame:
    """
    Strategy B Scorer (Intraday Choppy Mean Reversion Engine).
    
    Optimizes for VWAP fades & price exhaustion:
      - 40% Fade & Exhaustion Score (s_vwap_fade + s_exhaustion + s_sr)
      - 35% Deep ITM Delta Quality (peak at |delta| = 0.78 for 1:1 spot tracking)
      - 15% Theta Decay Shield (low theta bleed relative to LTP)
      - 10% Spread Quality
    """
    if df.is_empty():
        return df

    # 1. Exhaustion, Fade & S/R Quality (40%)
    if "s_vwap_fade" in df.columns and "s_exhaustion" in df.columns:
        fade_val = pl.col("s_vwap_fade") + pl.col("s_exhaustion")
        if "s_sr" in df.columns:
            fade_val = fade_val + pl.col("s_sr").abs() * 0.5
        fade_val = fade_val.clip(1.0, 5.0)
        fade_score = (fade_val - 1.0) / 4.0 * 100.0
    else:
        fade_score = pl.lit(60.0)

    # 2. Deep ITM Delta Quality (35%) — Peak at |delta| = 0.78 (Theta-immune fade)
    if "delta" in df.columns:
        delta_quality = (1.0 - ((pl.col("delta").abs() - 0.78).abs() / 0.20)).clip(0.0, 1.0) * 100.0
    else:
        delta_quality = pl.lit(60.0)

    # 3. Theta Decay Shield (15%)
    if "theta" in df.columns and "ltp" in df.columns:
        theta_ratio = pl.when(pl.col("ltp") > 0).then(pl.col("theta").abs() / pl.col("ltp")).otherwise(0.10)
        theta_shield = ((0.12 - theta_ratio) / 0.10).clip(0.0, 1.0) * 100.0
    else:
        theta_shield = pl.lit(60.0)

    # 4. Spread Quality (10%)
    if "bid" in df.columns and "ask" in df.columns:
        mid = (pl.col("bid") + pl.col("ask")) / 2.0
        spread_pct = pl.when(mid > 0).then((pl.col("ask") - pl.col("bid")) / mid).otherwise(0.02)
        spread_quality = ((0.015 - spread_pct) / 0.01).clip(0.0, 1.0) * 100.0
    else:
        spread_quality = pl.lit(50.0)

    df = df.with_columns(
        (fade_score * 0.40 + delta_quality * 0.35 + theta_shield * 0.15 + spread_quality * 0.10)
        .fill_null(0.0).fill_nan(0.0)
        .alias("opportunity_score")
    )
    df = df.with_columns(pl.col("opportunity_score").alias("selection_score"))
    df = df.with_columns([
        pl.col("opportunity_score").alias("c_signal"),
        pl.lit(0.0).alias("c_vwoim"),
        pl.lit(0.0).alias("c_oi"),
        pl.lit(0.0).alias("c_regime"),
        pl.lit(0.0).alias("c_spread"),
        pl.lit(0.0).alias("c_latency")
    ])
    return df


def score_closing_auction_opportunities(df: pl.DataFrame) -> pl.DataFrame:
    """
    Strategy C Scorer (Daily Closing Auction Session Imbalance Engine, 3:15 - 3:35 PM).
    
    Optimizes for EOD Closing Auction Imbalance Spikes:
      - 40% Closing Imbalance & Discovered VWAP Gap
      - 30% ATM Delta Quality (peak at |delta| = 0.50, premium <= 150)
      - 20% Order Book Ask Sweep (s_ba_press)
      - 10% Spread Quality
    """
    if df.is_empty():
        return df

    # 1. Closing Imbalance / VWAP Gap (40%)
    if "composite_alpha_score" in df.columns:
        imb_score = (pl.col("composite_alpha_score").clip(5.0, 35.0) - 5.0) / 30.0 * 100.0
    else:
        imb_score = pl.lit(70.0)

    # 2. ATM Gamma & Premium Quality (30%)
    if "delta" in df.columns:
        delta_qual = (1.0 - ((pl.col("delta").abs() - 0.50).abs() / 0.20)).clip(0.0, 1.0) * 100.0
    else:
        delta_qual = pl.lit(70.0)

    if "ltp" in df.columns:
        prem_bonus = pl.when(pl.col("ltp") <= 150).then(1.2).otherwise(0.8)
        delta_qual = (delta_qual * prem_bonus).clip(0.0, 100.0)

    # 3. Order Book Ask Sweep (20%)
    if "s_ba_press" in df.columns:
        sweep_qual = (pl.col("s_ba_press").clip(lower_bound=0.0) * 20.0).clip(0.0, 100.0)
    else:
        sweep_qual = pl.lit(60.0)

    # 4. Spread Quality (10%)
    if "bid" in df.columns and "ask" in df.columns:
        mid = (pl.col("bid") + pl.col("ask")) / 2.0
        spread_pct = pl.when(mid > 0).then((pl.col("ask") - pl.col("bid")) / mid).otherwise(0.02)
        spread_quality = ((0.015 - spread_pct) / 0.01).clip(0.0, 1.0) * 100.0
    else:
        spread_quality = pl.lit(50.0)

    df = df.with_columns(
        (imb_score * 0.40 + delta_qual * 0.30 + sweep_qual * 0.20 + spread_quality * 0.10)
        .fill_null(0.0).fill_nan(0.0)
        .alias("opportunity_score")
    )
    df = df.with_columns(pl.col("opportunity_score").alias("selection_score"))
    df = df.with_columns([
        pl.col("opportunity_score").alias("c_signal"),
        pl.lit(0.0).alias("c_vwoim"),
        pl.lit(0.0).alias("c_oi"),
        pl.lit(0.0).alias("c_regime"),
        pl.lit(0.0).alias("c_spread"),
        pl.lit(0.0).alias("c_latency")
    ])
    return df


def score_expiry_gamma_opportunities(df: pl.DataFrame) -> pl.DataFrame:
    """
    Strategy D Scorer (Expiry Power Hour Short Covering Panic Engine, 2:45 - 3:35 PM Expiry Days).
    
    Optimizes for Short Covering Panic Signatures:
      - 40% Short Covering Panic (delta_oi drop + delta_volume surge + ask sweep)
      - 35% ATM Gamma Reactivity (peak at |delta| = 0.50)
      - 15% Volume Surge
      - 10% Spread Quality
    """
    if df.is_empty():
        return df

    # 1. Short Covering Panic Signature (40%)
    if "delta_oi" in df.columns and "delta_volume" in df.columns:
        panic_score = (
            (pl.col("delta_oi").abs() / 20.0 + pl.col("delta_volume") / 100.0)
            .clip(0.0, 100.0)
        )
    else:
        panic_score = pl.lit(40.0)

    # 2. ATM Gamma Reactivity (35%)
    if "delta" in df.columns:
        gamma_qual = (1.0 - ((pl.col("delta").abs() - 0.50).abs() / 0.20)).clip(0.0, 1.0) * 100.0
    else:
        gamma_qual = pl.lit(70.0)

    # 3. Volume Surge (15%)
    if "volume" in df.columns:
        vol_qual = (pl.col("volume").log1p() / (pl.col("volume").log1p().max() + 1e-5)).fill_null(0.6) * 100.0
    else:
        vol_qual = pl.lit(60.0)

    # 4. Spread Quality (10%)
    if "bid" in df.columns and "ask" in df.columns:
        mid = (pl.col("bid") + pl.col("ask")) / 2.0
        spread_pct = pl.when(mid > 0).then((pl.col("ask") - pl.col("bid")) / mid).otherwise(0.02)
        spread_quality = ((0.015 - spread_pct) / 0.01).clip(0.0, 1.0) * 100.0
    else:
        spread_quality = pl.lit(50.0)

    df = df.with_columns(
        (panic_score * 0.40 + gamma_qual * 0.35 + vol_qual * 0.15 + spread_quality * 0.10)
        .fill_null(0.0).fill_nan(0.0)
        .alias("opportunity_score")
    )
    df = df.with_columns(pl.col("opportunity_score").alias("selection_score"))
    df = df.with_columns([
        pl.col("opportunity_score").alias("c_signal"),
        pl.lit(0.0).alias("c_vwoim"),
        pl.lit(0.0).alias("c_oi"),
        pl.lit(0.0).alias("c_regime"),
        pl.lit(0.0).alias("c_spread"),
        pl.lit(0.0).alias("c_latency")
    ])
    return df

