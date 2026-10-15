"""
NSE Option Chain Intelligence Signals.

Extracts market structure signals from the full NSE option chain:
- Put-Call Ratio (PCR) and PCR trend
- Max Pain and distance from spot
- OI concentration levels (support/resistance)
- IV Skew
- Total buildup/unwinding

These signals provide independent confirmation from exchange-level data,
separate from the WebSocket tick feed.
"""
import polars as pl
from loguru import logger
from typing import Dict, Any, Optional, List
import time

_smoothed_state: Dict[str, Dict[str, float]] = {}


class NSESignalExtractor:
    """Extracts and caches market structure signals from NSE option chain data."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_update: Dict[str, float] = {}

    def extract(self, symbol: str, chain_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract all market structure signals from NSE option chain JSON.
        Returns a dict of computed signals.
        """
        if not chain_data or "records" not in chain_data:
            return self._cache.get(symbol, self._empty_signals())

        records = chain_data["records"]
        data_list = records.get("data", [])
        underlying_val = records.get("underlyingValue", 0)

        if not data_list or not underlying_val:
            return self._cache.get(symbol, self._empty_signals())

        # v3 API: data is already filtered by expiry (specified in URL)
        # No need to filter by expiryDate — use all data
        
        # Use 'filtered' section for accurate totals (v3 provides pre-computed totals)
        filtered = chain_data.get("filtered", {})
        
        signals = self._compute_signals(data_list, underlying_val, symbol, filtered)
        self._cache[symbol] = signals
        self._last_update[symbol] = time.time()
        return signals

    def _compute_signals(self, data: List[Dict], spot: float, symbol: str,
                          filtered: Dict = None) -> Dict[str, Any]:
        """Compute all market structure signals."""
        total_ce_oi = 0
        total_pe_oi = 0
        total_ce_vol = 0
        total_pe_vol = 0
        strike_oi = {}  # {strike: {"ce_oi": x, "pe_oi": y, "ce_iv": z, "pe_iv": w}}

        for item in data:
            strike = item.get("strikePrice", 0)
            if strike not in strike_oi:
                strike_oi[strike] = {"ce_oi": 0, "pe_oi": 0, "ce_iv": 0, "pe_iv": 0,
                                     "ce_chg_oi": 0, "pe_chg_oi": 0, "ce_vol": 0, "pe_vol": 0}

            ce = item.get("CE", {})
            pe = item.get("PE", {})

            if ce:
                oi = ce.get("openInterest", 0) or 0
                total_ce_oi += oi
                total_ce_vol += ce.get("totalTradedVolume", 0) or 0
                strike_oi[strike]["ce_oi"] = oi
                strike_oi[strike]["ce_iv"] = ce.get("impliedVolatility", 0) or 0
                strike_oi[strike]["ce_chg_oi"] = ce.get("changeinOpenInterest", 0) or 0
                strike_oi[strike]["ce_vol"] = ce.get("totalTradedVolume", 0) or 0

            if pe:
                oi = pe.get("openInterest", 0) or 0
                total_pe_oi += oi
                total_pe_vol += pe.get("totalTradedVolume", 0) or 0
                strike_oi[strike]["pe_oi"] = oi
                strike_oi[strike]["pe_iv"] = pe.get("impliedVolatility", 0) or 0
                strike_oi[strike]["pe_chg_oi"] = pe.get("changeinOpenInterest", 0) or 0
                strike_oi[strike]["pe_vol"] = pe.get("totalTradedVolume", 0) or 0

        # Use filtered totals from v3 API if available (more accurate than summing)
        if filtered:
            f_ce = filtered.get("CE", {})
            f_pe = filtered.get("PE", {})
            if f_ce.get("totOI", 0):
                total_ce_oi = f_ce["totOI"]
            if f_pe.get("totOI", 0):
                total_pe_oi = f_pe["totOI"]
            if f_ce.get("totVol", 0):
                total_ce_vol = f_ce["totVol"]
            if f_pe.get("totVol", 0):
                total_pe_vol = f_pe["totVol"]

        # --- 1. PCR (Put-Call Ratio) ---
        pcr_oi = total_pe_oi / (total_ce_oi + 1) if total_ce_oi > 0 else 1.0
        pcr_vol = total_pe_vol / (total_ce_vol + 1) if total_ce_vol > 0 else 1.0

        # --- 2. Max Pain ---
        max_pain = self._compute_max_pain(strike_oi, spot)

        # --- 3. OI Concentration (support/resistance) ---
        max_ce_oi_strike = max(strike_oi, key=lambda s: strike_oi[s]["ce_oi"]) if strike_oi else spot
        max_pe_oi_strike = max(strike_oi, key=lambda s: strike_oi[s]["pe_oi"]) if strike_oi else spot

        # --- 4. IV Skew ---
        atm_strike = min(strike_oi.keys(), key=lambda s: abs(s - spot)) if strike_oi else spot
        atm_ce_iv = strike_oi.get(atm_strike, {}).get("ce_iv", 0)
        atm_pe_iv = strike_oi.get(atm_strike, {}).get("pe_iv", 0)

        # --- 5. OI Buildup Direction ---
        total_ce_buildup = sum(d["ce_chg_oi"] for d in strike_oi.values())
        total_pe_buildup = sum(d["pe_chg_oi"] for d in strike_oi.values())
        buildup_ratio = total_pe_buildup / (abs(total_ce_buildup) + 1) if total_ce_buildup != 0 else 1.0

        return {
            "spot": spot,
            "pcr_oi": round(pcr_oi, 4),
            "pcr_vol": round(pcr_vol, 4),
            "max_pain": max_pain,
            "max_pain_dist_pct": round((spot - max_pain) / spot * 100, 2) if spot > 0 else 0,
            "resistance_strike": max_ce_oi_strike,  # Highest CE OI = resistance
            "support_strike": max_pe_oi_strike,      # Highest PE OI = support
            "atm_ce_iv": atm_ce_iv,
            "atm_pe_iv": atm_pe_iv,
            "iv_skew": round(atm_pe_iv - atm_ce_iv, 2),  # +ve = put demand (fear)
            "ce_buildup": total_ce_buildup,
            "pe_buildup": total_pe_buildup,
            "buildup_ratio": round(buildup_ratio, 4),
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            # Per-strike IV map for execution optimizer (Delta calculation)
            "strike_iv_map": {s: {"ce_iv": d["ce_iv"], "pe_iv": d["pe_iv"]} for s, d in strike_oi.items()},
        }

    def _compute_max_pain(self, strike_oi: Dict, spot: float) -> float:
        """
        Max Pain = strike where total option buyer loss is maximum
        (or equivalently, where option writers profit the most).
        """
        if not strike_oi:
            return spot

        strikes = sorted(strike_oi.keys())
        min_pain = float("inf")
        max_pain_strike = spot

        for test_strike in strikes:
            total_pain = 0
            for s, data in strike_oi.items():
                # CE pain: if spot (test_strike) > strike, CE is ITM
                if test_strike > s:
                    total_pain += (test_strike - s) * data["ce_oi"]
                # PE pain: if spot (test_strike) < strike, PE is ITM
                if test_strike < s:
                    total_pain += (s - test_strike) * data["pe_oi"]

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike

        return max_pain_strike

    def _empty_signals(self) -> Dict[str, Any]:
        return {
            "spot": 0, "pcr_oi": 1.0, "pcr_vol": 1.0,
            "max_pain": 0, "max_pain_dist_pct": 0,
            "resistance_strike": 0, "support_strike": 0,
            "atm_ce_iv": 0, "atm_pe_iv": 0, "iv_skew": 0,
            "ce_buildup": 0, "pe_buildup": 0, "buildup_ratio": 1.0,
            "total_ce_oi": 0, "total_pe_oi": 0,
        }

    def get_cached(self, symbol: str) -> Dict[str, Any]:
        """Get last computed signals (for pipeline use without re-fetching)."""
        return self._cache.get(symbol, self._empty_signals())


def enrich_with_nse_signals(df: pl.DataFrame, nse_signals: Dict[str, Dict[str, Any]]) -> pl.DataFrame:
    """
    Add NSE market structure columns to the feature DataFrame.
    nse_signals: {"NIFTY": {...}, "BANKNIFTY": {...}}
    """
    if df.is_empty() or "underlying" not in df.columns:
        return df

    global _smoothed_state
    alpha = 0.10  # 10% weight to new value per tick (smooths over ~10-20 seconds)
    
    # Apply EMA smoothing to the structural signals to prevent Scoring Shock
    for sym, signals in nse_signals.items():
        if sym not in _smoothed_state:
            _smoothed_state[sym] = {
                "max_pain_dist_pct": signals.get("max_pain_dist_pct", 0.0),
                "iv_skew": signals.get("iv_skew", 0.0),
                "pcr_oi": signals.get("pcr_oi", 1.0)
            }
        else:
            prev = _smoothed_state[sym]
            prev["max_pain_dist_pct"] = (1 - alpha) * prev["max_pain_dist_pct"] + alpha * signals.get("max_pain_dist_pct", 0.0)
            prev["iv_skew"] = (1 - alpha) * prev["iv_skew"] + alpha * signals.get("iv_skew", 0.0)
            prev["pcr_oi"] = (1 - alpha) * prev["pcr_oi"] + alpha * signals.get("pcr_oi", 1.0)
            
            # Override the raw signals in the dictionary so the smoothed values are mapped below
            signals["max_pain_dist_pct"] = prev["max_pain_dist_pct"]
            signals["iv_skew"] = prev["iv_skew"]
            signals["pcr_oi"] = prev["pcr_oi"]

    # Add signal columns per underlying
    for col_name in ["pcr_oi", "max_pain_dist_pct", "iv_skew", "buildup_ratio",
                      "support_strike", "resistance_strike"]:
        df = df.with_columns(
            pl.col("underlying").replace_strict(
                {sym: signals.get(col_name, 0) for sym, signals in nse_signals.items()},
                default=0
            ).cast(pl.Float64).alias(f"nse_{col_name}")
        )

    # Distance from support/resistance (useful for entry timing)
    if "strike" in df.columns:
        df = df.with_columns([
            ((pl.col("strike") - pl.col("nse_support_strike"))
             / (pl.col("strike") + 1e-8)).alias("nse_dist_from_support"),
            ((pl.col("nse_resistance_strike") - pl.col("strike"))
             / (pl.col("strike") + 1e-8)).alias("nse_dist_from_resistance"),
        ])

    return df
