import polars as pl
import numpy as np

def validate_regimes(df: pl.DataFrame, target_col: str = "future_move_pct_15m") -> dict:
    """
    Evaluates top features' performance across regimes.
    """
    if df.is_empty() or "volatility_regime" not in df.columns or target_col not in df.columns:
        return {}
        
    valid_df = df.drop_nulls(subset=["volatility_regime", target_col])
    if valid_df.height < 10:
        return {}
        
    try:
        # Determine regime thresholds
        vol_median = valid_df.select(pl.col("volatility_regime").median()).item()
        
        # High vol vs Low vol dataframes
        high_vol_df = valid_df.filter(pl.col("volatility_regime") > vol_median)
        low_vol_df = valid_df.filter(pl.col("volatility_regime") <= vol_median)
        
        # Compression df
        compression_df = valid_df.filter(pl.col("compression_score") < 1.2) if "compression_score" in valid_df.columns else valid_df
        
        # Trend df
        trend_df = valid_df.filter(pl.col("trend_regime").abs() > 0.005) if "trend_regime" in valid_df.columns else valid_df
        
        # Function to compute IC for a feature in a df
        def get_ic(d, feature):
            if d.height < 5 or feature not in d.columns: return 0.0
            ic = d.select(pl.corr(feature, target_col, method="pearson")).item()
            return float(ic) if ic is not None else 0.0
            
        # We will just evaluate a representative feature, e.g., vwoim_smoothed or a composite
        rep_feature = "vwoim_smoothed" if "vwoim_smoothed" in valid_df.columns else "oi_flow_score"
        if rep_feature not in valid_df.columns:
            return {}
            
        high_vol_ic = get_ic(high_vol_df, rep_feature)
        low_vol_ic = get_ic(low_vol_df, rep_feature)
        comp_ic = get_ic(compression_df, rep_feature)
        trend_ic = get_ic(trend_df, rep_feature)
        
        # Regime score is stability across regimes. Penalize if variance of ICs is high
        ics = [high_vol_ic, low_vol_ic, comp_ic, trend_ic]
        avg_ic = np.mean(ics)
        std_ic = np.std(ics)
        
        regime_score = avg_ic / (std_ic + 1e-6)
        
        return {
            "high_vol_ic": high_vol_ic,
            "low_vol_ic": low_vol_ic,
            "compression_ic": comp_ic,
            "trend_ic": trend_ic,
            "regime_score": float(regime_score)
        }
    except Exception:
        return {}
