import polars as pl

def compute_gex_proxy(df: pl.DataFrame) -> pl.DataFrame:
    """
    Computes proxy features for Gamma Exposure (GEX) and Liquidity.
    gex_proxy: Proxy for Gamma (highest at ATM, scales with OI)
    oi_density: Ratio of OI at this strike to total OI for this expiry
    liquidity_wall_score: Ratio of OI to average OI for this expiry
    """
    if df.is_empty():
        return df
        
    pk_exp = ["timestamp", "underlying", "expiry", "option_type"]
    
    # Calculate Total OI and Average OI per expiry/timestamp
    df = df.with_columns([
        pl.col("oi").sum().over(pk_exp).alias("total_oi"),
        pl.col("oi").mean().over(pk_exp).alias("avg_oi")
    ])
    
    epsilon = 1e-8
    
    # 1. GEX Proxy
    # Gamma is highest ATM and decays as distance increases.
    # We use: OI / (1 + abs(atm_distance) / strike)
    # Wait, atm_distance is absolute difference in strike points. 
    # Let's normalize it by strike: pct_distance = abs(atm_distance) / strike
    # gex_proxy = OI * exp(-pct_distance * 100)
    df = df.with_columns([
        (pl.col("oi") * (-100.0 * pl.col("atm_distance").abs() / (pl.col("strike") + epsilon)).exp()).alias("gex_proxy")
    ])
    
    # 2. OI Density
    df = df.with_columns([
        (pl.col("oi") / (pl.col("total_oi") + epsilon)).alias("oi_density")
    ])
    
    # 3. Liquidity Wall Score
    df = df.with_columns([
        (pl.col("oi") / (pl.col("avg_oi") + epsilon)).alias("liquidity_wall_score")
    ])
    
    # Drop temp columns
    df = df.drop(["total_oi", "avg_oi"])
    
    return df
