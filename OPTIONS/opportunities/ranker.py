import polars as pl

def rank_opportunities(df: pl.DataFrame) -> pl.DataFrame:
    """
    Step 3: Strike Ranking
    
    REDESIGNED: Returns the TOP 1 candidate per underlying per timestamp.
    The old ranker kept top 5, causing 15 signals to flood the publisher.
    Since the scorer now properly discriminates between strikes,
    we only need the single best option contract per index.
    """
    if df.is_empty() or "opportunity_score" not in df.columns:
        return df
        
    score_col = "selection_score" if "selection_score" in df.columns else "opportunity_score"
    
    # Determine ranking partition keys
    rank_over = []
    if "timestamp" in df.columns:
        rank_over.append("timestamp")
    if "underlying" in df.columns:
        rank_over.append("underlying")
    
    if not rank_over:
        # Dry run fallback
        df = df.with_columns(pl.col(score_col).rank("ordinal", descending=True).alias("rank"))
        df = df.with_columns(pl.lit(1.0).alias("percentile"))
        return df.filter(pl.col("rank") <= 1)
    
    # Rank descending by score per (timestamp, underlying)
    df = df.with_columns([
        pl.col(score_col).rank("ordinal", descending=True).over(rank_over).alias("rank"),
        pl.col(score_col).rank("average", descending=True).over(rank_over).alias("avg_rank_temp"),
        pl.count(score_col).over(rank_over).alias("group_count")
    ])
    
    # Percentile
    df = df.with_columns([
        ((pl.col("group_count") - pl.col("avg_rank_temp") + 1) / pl.col("group_count")).alias("percentile")
    ])
    
    df = df.drop(["avg_rank_temp", "group_count"])
    
    # TOP 1 per underlying per timestamp — only the single best strike survives
    df = df.filter(pl.col("rank") <= 1)
    
    return df
