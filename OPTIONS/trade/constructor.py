import polars as pl
from trade.entry import apply_entry_logic
from trade.exit import apply_exit_logic
from trade.risk import apply_risk_logic
from trade.quality import validate_trades

def build_trade_candidates(df_opps: pl.DataFrame) -> pl.DataFrame:
    """
    Coordinates entry, exit, risk, and quality checks.
    """
    if df_opps is None or df_opps.is_empty():
        return pl.DataFrame()

    df = apply_entry_logic(df_opps)
    df = apply_exit_logic(df)
    df = apply_risk_logic(df)
    df = validate_trades(df)

    # Filter invalid
    df = df.filter(pl.col("is_valid_trade"))
    df = df.drop(["is_valid_trade"])

    # Ensure required schema elements are present
    required_cols = [
        "timestamp", "underlying", "expiry", "strike", "option_type",
        "entry_rule", "entry_price", "stop_rule", "stop_price",
        "target_rule", "target_price", "time_exit", "confidence", "expected_rr"
    ]
    
    # We might have missing columns depending on the raw opportunity schema.
    # Just select what we can, adding nulls for what we can't if absolutely necessary.
    for c in required_cols:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None).alias(c))

    # Keep underlying info and trade rules
    df = df.select(required_cols)

    return df
