import polars as pl

def build_composite_score(df: pl.DataFrame) -> pl.DataFrame:
    """
    Builds a composite alpha score based on combined normalized signal values.
    Scales from -100 to +100.
    """
    if df.is_empty():
        return df
        
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    # We combine 3 features to build a composite:
    # vwoim_smoothed, oi_flow_score, gex_proxy
    # We first compute cross-sectional z-scores across the universe for each timestamp
    # But since we may not have cross-sectional data nicely aligned, we just use a rolling z-score.
    
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    features = []
    if "vwoim_smoothed" in df.columns:
        df = df.with_columns(zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"))
        features.append("z_vwoim")
        
    if "oi_flow_score" in df.columns:
        df = df.with_columns(zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"))
        features.append("z_oi_flow")
        
    if "gex_proxy" in df.columns:
        df = df.with_columns(zscore("gex_proxy").fill_null(0).alias("z_gex"))
        features.append("z_gex")
        
    if not features:
        return df.with_columns(pl.lit(0.0).alias("composite_alpha_score"))
        
    # Sum the z-scores
    sum_expr = pl.sum_horizontal(features)
    
    df = df.with_columns(sum_expr.alias("raw_composite"))
    
    # Scale from -100 to +100 using a sigmoid or clip.
    # z-score sum of 3 could range from -10 to +10. Let's multiply by 20 and clip.
    df = df.with_columns(
        (pl.col("raw_composite") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    
    df = df.drop(features + ["raw_composite"])
    
    return df
