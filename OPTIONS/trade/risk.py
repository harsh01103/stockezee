import polars as pl

def apply_risk_logic(df: pl.DataFrame) -> pl.DataFrame:
    """
    Evaluates risk and computes expected RR.
    RR = Target Distance / Stop Distance
    Confidence = Copied from opportunity probability, defaulting to 0.5 if missing.
    """
    if df.is_empty():
        return df

    # Avoid division by zero or negative stop distance if prices are zero
    df = df.with_columns([
        (pl.col("target_price") - pl.col("entry_price")).abs().alias("target_dist"),
        (pl.col("entry_price") - pl.col("stop_price")).abs().alias("stop_dist")
    ])

    df = df.with_columns(
        pl.when(pl.col("stop_dist") > 0)
        .then(pl.col("target_dist") / pl.col("stop_dist"))
        .otherwise(0.0)
        .alias("expected_rr")
    )

    has_conf_in = "confidence" in df.columns
    if has_conf_in:
        input_conf = df["confidence"].clone()

    if "confidence" in df.columns:
        pass
    elif "probability" in df.columns:
        df = df.with_columns(pl.col("probability").alias("confidence"))
    elif "score" in df.columns:
        df = df.with_columns((pl.col("score") / 100.0).clip(0.0, 1.0).alias("confidence"))
    else:
        df = df.with_columns(pl.lit(0.5).alias("confidence"))

    if has_conf_in:
        max_diff = (df["confidence"] - input_conf).abs().max()
        assert max_diff is None or max_diff < 1e-6, "Confidence mutated during risk check"

    # Drop temporary dist columns
    df = df.drop(["target_dist", "stop_dist"])

    return df
