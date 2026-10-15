def run_momentum_engine(df_res, t0):
    """
    Strategy A: High-Conviction Momentum Breakouts
    Looks for explosive acceleration in price, volume, and OI.
    Requires TRENDING_MOMENTUM macro regime.
    """
    if df_res.is_empty():
        return pl.DataFrame(), 0
        
    # FIX #7: We need a minimum number of strikes to form a mathematical bell curve
    unique_strikes = df_res["strike"].n_unique()
    if unique_strikes < 5:
        log.warning("low_density=True  unique_strikes=%d  skipping momentum engine", unique_strikes)
        return pl.DataFrame(), 0
        
    # Trim deep OTM/ITM junk to prevent them from skewing the Z-scores
    if "delta" in df_res.columns:
        df_filtered = df_res.filter(
            (pl.col("volume") > 5000) & 
            (pl.col("delta").abs() >= 0.40) & 
            (pl.col("delta").abs() <= 0.70) &
            (((pl.col("ask") - pl.col("bid")) / ((pl.col("bid") + pl.col("ask")) / 2)) <= 0.015)
        )
        if df_filtered.height < 10:
            df_filtered = df_res.filter(
                (pl.col("volume") > 1000) &
                (pl.col("delta").abs() >= 0.35) & 
                (pl.col("delta").abs() <= 0.75) &
                (((pl.col("ask") - pl.col("bid")) / ((pl.col("bid") + pl.col("ask")) / 2)) <= 0.02)
            )
        df_res = df_filtered
    
    pk = ["underlying", "expiry", "strike", "option_type"]
    zscore_group = ["underlying", "option_type"]
    
    # ── COMPUTE RAW ROLLING FEATURES (Requires History) ──
    if "ltp" in df_res.columns:
        df_res = df_res.with_columns(
            ((pl.col("ltp") - pl.col("ltp").rolling_mean(3).over(pk)) / (pl.col("ltp").rolling_mean(3).over(pk) + 1e-8))
            .fill_null(0).fill_nan(0).alias("price_velocity")
        )
    if "delta_volume" in df_res.columns and "ltp" in df_res.columns:
        df_res = df_res.with_columns((pl.col("ltp") - pl.col("ltp").shift(1).over(pk)).fill_null(0).alias("_price_chg"))
        df_res = df_res.with_columns(
            (pl.col("delta_volume").abs() * pl.col("_price_chg").sign() / (pl.col("delta_volume").abs().rolling_mean(5).over(pk) + 1.0))
            .fill_null(0).fill_nan(0).clip(-20, 20).alias("volume_burst")
        )
        df_res = df_res.drop(["_price_chg"])
    if "delta_oi" in df_res.columns:
        df_res = df_res.with_columns((pl.col("delta_oi") - pl.col("delta_oi").shift(1).over(pk)).fill_null(0).alias("oi_accel"))
        if "bid" in df_res.columns and "ask" in df_res.columns:
            df_res = df_res.with_columns(((pl.col("ask") - pl.col("bid")).abs() / (((pl.col("ask") + pl.col("bid")) / 2) + 1e-8)).alias("_spread_pct"))
            df_res = df_res.with_columns(
                (pl.col("oi_accel") * pl.when(pl.col("_spread_pct") > 0.01).then(0.1).otherwise(1.0 - (pl.col("_spread_pct") * 50).clip(0, 0.9)))
                .alias("oi_accel")
            )
            df_res = df_res.drop(["_spread_pct"])
    
    # ── TAKE SNAPSHOT ──
    df_latest = df_res.unique(subset=pk, keep="last")
    if df_latest.is_empty():
        return pl.DataFrame(), 0
        
    scores = []
    
    # ── COMPUTE CROSS-SECTIONAL Z-SCORES ON SNAPSHOT ──
    if "price_velocity" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("price_velocity") - pl.col("price_velocity").mean().over(zscore_group)) / (pl.col("price_velocity").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_price_vel")
        )
        scores.append("s_price_vel")
    if "volume_burst" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("volume_burst") - pl.col("volume_burst").mean().over(zscore_group)) / (pl.col("volume_burst").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_vol_burst")
        )
        scores.append("s_vol_burst")
    if "oi_accel" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("oi_accel") - pl.col("oi_accel").mean().over(zscore_group)) / (pl.col("oi_accel").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_oi_accel")
        )
        scores.append("s_oi_accel")
    if "gamma" in df_latest.columns and "theta" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("gamma") - pl.col("gamma").mean().over(zscore_group)) / (pl.col("gamma").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_gamma"),
            ((pl.col("theta") - pl.col("theta").mean().over(zscore_group)) / (pl.col("theta").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_theta")
        )
        scores.extend(["s_gamma", "s_theta"])
        
    if "nse_dist_from_support" in df_latest.columns and "nse_dist_from_resistance" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((-pl.col("nse_dist_from_support").abs() + pl.col("nse_dist_from_resistance").abs()) * 5.0)
            .fill_null(0).fill_nan(0).clip(-3, 3).alias("s_sr")
        )
        scores.append("s_sr")
    if "ema_cross_pct" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("ema_cross_pct") - pl.col("ema_cross_pct").mean().over(zscore_group)) / (pl.col("ema_cross_pct").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_ema_cross")
        )
        scores.append("s_ema_cross")
    if "vwap_deviation" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("vwap_deviation") - pl.col("vwap_deviation").mean().over(zscore_group)) / (pl.col("vwap_deviation").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_vwap")
        )
        scores.append("s_vwap")
    if "dpcr_dt" in df_latest.columns and "option_type" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("dpcr_dt") * 10.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1))
            .fill_null(0).fill_nan(0).alias("s_pcr")
        )
        scores.append("s_pcr")
    elif "nse_pcr_oi" in df_latest.columns and "option_type" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (((pl.col("nse_pcr_oi") - 1.0) * 2.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1))
            .fill_null(0).fill_nan(0).alias("s_pcr")
        )
        scores.append("s_pcr")
    if "nse_max_pain_dist_pct" in df_latest.columns:
        df_latest = df_latest.with_columns((pl.col("nse_max_pain_dist_pct").abs() / 2.0).fill_null(0).fill_nan(0).alias("s_maxpain"))
        scores.append("s_maxpain")
    if "nse_iv_skew" in df_latest.columns:
        df_latest = df_latest.with_columns((pl.col("nse_iv_skew") / 5.0).fill_null(0).fill_nan(0).alias("s_iv_skew"))
        scores.append("s_iv_skew")
    if "bid" in df_latest.columns and "ask" in df_latest.columns and "ltp" in df_latest.columns:
        df_latest = df_latest.with_columns(
            pl.when((pl.col("ltp") - pl.col("bid")) > 0.0)
            .then((pl.col("ask") - pl.col("ltp")) / (pl.col("ltp") - pl.col("bid") + 1e-5))
            .otherwise(1.0).clip(0.1, 10.0).alias("ba_pressure")
        )
        df_latest = df_latest.with_columns(
            ((pl.col("ba_pressure") - pl.col("ba_pressure").mean().over(zscore_group)) / (pl.col("ba_pressure").std().over(zscore_group) + 1e-8))
            .fill_null(0).fill_nan(0).alias("s_ba_press")
        )
        scores.append("s_ba_press")
        
    if not scores:
        return pl.DataFrame(), 0
        
    weights = SCORE_WEIGHTS.copy()
    now_hour = datetime.now().hour
    now_minute = datetime.now().minute
    if now_hour < 10 or (now_hour == 10 and now_minute < 15):
        weights["s_price_vel"] *= 0.25
        weights["s_vol_burst"] *= 0.25
        weights["s_oi_accel"] *= 0.25
        
    weighted_terms = [pl.col(s) * weights.get(s, 0.05) for s in scores]
    df_latest = df_latest.with_columns(pl.sum_horizontal(weighted_terms).alias("raw_score"))
    df_latest = df_latest.with_columns((pl.col("raw_score") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score"))
    
    if "strike" in df_latest.columns:
        df_latest = df_latest.filter(pl.col("strike") > 0)
        
    df_latest = df_latest.with_columns(pl.lit(True).alias("is_trending"))
    df_univ = build_universe(df_latest)
    if df_univ.is_empty():
        return pl.DataFrame(), round(time.time() - t0, 2)
        
    df_scored = score_opportunities(df_univ)
    df_ranked = rank_opportunities(df_scored)
    df_conf = calculate_confidence(df_ranked)
    df_conf = df_conf.with_columns(pl.lit("BUY").alias("action"))
    
    elapsed = round(time.time() - t0, 2)
    return df_conf, elapsed
