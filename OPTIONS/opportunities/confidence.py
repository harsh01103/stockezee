import polars as pl

def calculate_confidence(df: pl.DataFrame) -> pl.DataFrame:
    """
    Backward-compatible entry point for Strategy A Momentum Confidence.
    """
    return calculate_strategy_confidence(df, "Momentum Breakout")


def calculate_strategy_confidence(df: pl.DataFrame, engine_type: str = "Momentum Breakout", macro_data: dict = None) -> pl.DataFrame:
    """
    Decoupled Confidence Calculator for Strategies A, B, C, and D.
    
    - Strategy A (Momentum Breakout): Direct mapping up to 0.95 with Deep OTM penalties & macro alignment.
    - Strategy B (Mean Reversion): Direct mapping (0.60 - 0.82) WITHOUT Deep ITM penalties (Deep ITM is desired).
    - Strategy C (Closing Auction Session): Direct mapping (0.72 - 0.90) for daily EOD closing imbalances.
    - Strategy D (Expiry Power Hour Gamma): Direct mapping (0.75 - 0.95) for short covering panic squeezes.
    """
    if df.is_empty():
        return df
        
    if "opportunity_score" not in df.columns:
        return df
        
    # Base confidence = opportunity_score / 100.0
    df = df.with_columns([
        (pl.col("opportunity_score") / 100.0).alias("base_confidence")
    ])

    # Macro & Fundamental Sentiment Adjustment per Underlying
    macro_conf_shift = 0.0
    fund_bn_shift = 0.0
    fund_nifty_shift = 0.0

    if macro_data and isinstance(macro_data, dict):
        macro_risk = macro_data.get("risk_level", "LOW")
        if macro_risk == "HIGH" and engine_type == "Momentum Breakout":
            macro_conf_shift = -0.05
        elif macro_risk == "LOW":
            macro_conf_shift = 0.02

        bn_fund = macro_data.get("banknifty_fundamental_score", 0.0)
        nifty_fund = macro_data.get("nifty_fundamental_score", 0.0)

        if bn_fund >= 15.0: fund_bn_shift = 0.03
        elif bn_fund <= -15.0: fund_bn_shift = -0.03

        if nifty_fund >= 15.0: fund_nifty_shift = 0.03
        elif nifty_fund <= -15.0: fund_nifty_shift = -0.03

    if "underlying" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("underlying") == "BANKNIFTY").then(pl.lit(fund_bn_shift))
            .when(pl.col("underlying") == "NIFTY").then(pl.lit(fund_nifty_shift))
            .otherwise(pl.lit(0.0))
            .alias("fund_shift")
        )
    else:
        df = df.with_columns(pl.lit(0.0).alias("fund_shift"))

    if engine_type == "Mean Reversion":
        # Strategy B: Mean Reversion confidence mapping
        # Does NOT penalize Deep ITM options (Delta > 0.70 is desired for theta-immune fades)
        df = df.with_columns(
            (pl.col("base_confidence") + macro_conf_shift + pl.col("fund_shift")).clip(0.60, 0.82).alias("confidence")
        )
    elif engine_type == "Closing Auction":
        # Strategy C: Closing Auction Imbalance Session (Daily 3:15-3:35 PM)
        df = df.with_columns(
            (pl.col("base_confidence") + macro_conf_shift + pl.col("fund_shift")).clip(0.72, 0.90).alias("confidence")
        )
    elif engine_type in ("Power Hour", "Expiry Gamma"):
        # Strategy D: Expiry Power Hour Gamma Squeeze (Expiry 2:45-3:35 PM)
        df = df.with_columns(
            (pl.col("base_confidence") + macro_conf_shift + pl.col("fund_shift")).clip(0.75, 0.95).alias("confidence")
        )
    else:
        # Strategy A: Momentum Breakout confidence mapping
        delta_penalty = pl.lit(0.0)
        if "delta" in df.columns:
            abs_delta = pl.col("delta").abs()
            delta_penalty = pl.when(abs_delta < 0.30).then((0.30 - abs_delta) * 0.5).otherwise(0.0)
            
        theta_penalty = pl.lit(0.0)
        if "theta" in df.columns and "ltp" in df.columns:
            theta_ratio = pl.when(pl.col("ltp") > 0).then(pl.col("theta").abs() / pl.col("ltp")).otherwise(0.0)
            theta_penalty = pl.when(theta_ratio > 0.15).then((theta_ratio - 0.15) * 0.3).otherwise(0.0)
            theta_penalty = theta_penalty.clip(0.0, 0.10)
            
        df = df.with_columns([
            (pl.col("base_confidence") - delta_penalty - theta_penalty + macro_conf_shift + pl.col("fund_shift")).alias("confidence")
        ])
        
        if "is_trending" in df.columns:
            df = df.with_columns(
                pl.when(pl.col("is_trending") == False)
                .then(pl.col("confidence").clip(0.0, 0.65))
                .otherwise(pl.col("confidence").clip(0.0, 0.95))
                .alias("confidence")
            )
        else:
            df = df.with_columns(pl.col("confidence").clip(0.0, 0.95))

    if "base_confidence" in df.columns:
        df = df.drop(["base_confidence", "fund_shift"], strict=False)
        
    return df


