import polars as pl
import numpy as np

def build_universe(df: pl.DataFrame, available_capital: float = 30000.0) -> pl.DataFrame:
    """
    Backward-compatible entry point for Strategy A Momentum Universe.
    """
    return build_momentum_universe(df, available_capital)


def build_momentum_universe(df: pl.DataFrame, available_capital: float = 30000.0) -> pl.DataFrame:
    """
    Universe Builder for Strategy A (Momentum Breakout).
    Ranks strikes by proximity to ITM Delta ~ 0.65.
    """
    if df.is_empty():
        return df

    df = df.filter(pl.col("underlying").is_in(["NIFTY", "BANKNIFTY"]))
    if df.height == 0 or "spot" not in df.columns:
        return df

    if "delta" in df.columns:
        target_delta = 0.65
        df = df.with_columns((pl.col("delta").abs() - target_delta).abs().alias("strike_rank_metric"))
    else:
        df = df.with_columns((pl.col("strike") - pl.col("spot")).abs().alias("strike_rank_metric"))
    
    pk_expiry = ["timestamp", "underlying", "expiry", "option_type"]
    available_pks = [c for c in pk_expiry if c in df.columns]
    if available_pks:
        df = df.with_columns(pl.col("strike_rank_metric").rank("ordinal").over(available_pks).alias("expiry_strike_rank"))
        df = df.filter(pl.col("expiry_strike_rank") <= 10)

    score_col = "composite_alpha_score" if "composite_alpha_score" in df.columns else "strike_rank_metric"
    descending = score_col == "composite_alpha_score"
    df = df.sort(score_col, descending=descending)
    return df


def build_mean_reversion_universe(df: pl.DataFrame, available_capital: float = 30000.0) -> pl.DataFrame:
    """
    Universe Builder for Strategy B (Intraday Choppy Mean Reversion).
    Ranks strikes by proximity to Deep ITM Delta ~ 0.78 for theta immunity and 1:1 spot tracking.
    """
    if df.is_empty():
        return df

    df = df.filter(pl.col("underlying").is_in(["NIFTY", "BANKNIFTY"]))
    if df.height == 0 or "spot" not in df.columns:
        return df

    if "delta" in df.columns:
        target_delta = 0.78
        df = df.with_columns((pl.col("delta").abs() - target_delta).abs().alias("strike_rank_metric"))
    else:
        df = df.with_columns((pl.col("strike") - pl.col("spot")).abs().alias("strike_rank_metric"))

    pk_expiry = ["timestamp", "underlying", "expiry", "option_type"]
    available_pks = [c for c in pk_expiry if c in df.columns]
    if available_pks:
        df = df.with_columns(pl.col("strike_rank_metric").rank("ordinal").over(available_pks).alias("expiry_strike_rank"))
        df = df.filter(pl.col("expiry_strike_rank") <= 10)

    score_col = "s_vwap_fade" if "s_vwap_fade" in df.columns else "strike_rank_metric"
    df = df.sort(score_col, descending=True)
    return df


def build_closing_auction_universe(df: pl.DataFrame, available_capital: float = 30000.0) -> pl.DataFrame:
    """
    Universe Builder for Strategy C (Closing Auction & Power Hour Engine).
    Ranks strikes by proximity to ATM Delta ~ 0.50 with premium <= 150 for maximum Gamma explosion.
    """
    if df.is_empty():
        return df

    df = df.filter(pl.col("underlying").is_in(["NIFTY", "BANKNIFTY"]))
    if df.height == 0 or "spot" not in df.columns:
        return df

    if "delta" in df.columns:
        target_delta = 0.50
        df = df.with_columns((pl.col("delta").abs() - target_delta).abs().alias("strike_rank_metric"))
    else:
        df = df.with_columns((pl.col("strike") - pl.col("spot")).abs().alias("strike_rank_metric"))

    # Premium affordability filter for CAS Gamma (LTP <= 150)
    if "ltp" in df.columns:
        df = df.filter(pl.col("ltp") <= 180)

    pk_expiry = ["timestamp", "underlying", "expiry", "option_type"]
    available_pks = [c for c in pk_expiry if c in df.columns]
    if available_pks:
        df = df.with_columns(pl.col("strike_rank_metric").rank("ordinal").over(available_pks).alias("expiry_strike_rank"))
        df = df.filter(pl.col("expiry_strike_rank") <= 5)

    df = df.sort("strike_rank_metric", descending=False)
    
    df = df.drop(["strike_rank_metric", "expiry_strike_rank"], strict=False)
        
    return df
