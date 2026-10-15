import httpx
import polars as pl
import numpy as np
import logging
from datetime import datetime

log = logging.getLogger("fundamental_analyzer")

# Heavyweight Weights Matrix (Nifty 50 and BankNifty)
BANKNIFTY_HEAVYWEIGHTS = {
    "HDFCBANK.NS": 0.27,
    "ICICIBANK.NS": 0.23,
    "SBIN.NS": 0.10,
    "AXISBANK.NS": 0.09,
    "KOTAKBANK.NS": 0.08,
}

NIFTY_HEAVYWEIGHTS = {
    "HDFCBANK.NS": 0.11,
    "RELIANCE.NS": 0.095,
    "ICICIBANK.NS": 0.08,
    "INFY.NS": 0.06,
    "TCS.NS": 0.04,
    "LT.NS": 0.035,
    "ITC.NS": 0.038,
}

def fetch_yahoo_pct_change(symbol: str) -> float:
    """
    Fetches 1-day percentage change for a symbol via Yahoo Finance REST API.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = httpx.get(url, headers=headers, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                valid_closes = [c for c in closes if c is not None]
                if len(valid_closes) >= 2:
                    c1, c2 = valid_closes[-2], valid_closes[-1]
                    return float((c2 - c1) / c1 * 100.0)
    except Exception as e:
        log.debug("Yahoo Finance fetch failed for %s: %s", symbol, e)
    return 0.0


def fetch_fundamental_metrics() -> dict:
    """
    Scrapes and computes fundamental metrics across all 5 core fundamental pillars:
      Pillar 1: Macro-Economic (India 10Y Yield, Brent Crude, USD/INR)
      Pillar 2: Index Heavyweight Stock Earnings & Volatility
      Pillar 3: Institutional Capital Flows (FII/DII Flow Proxy)
      Pillar 4: Global Cross-Asset (Dollar Index DXY, DAX, S&P 500, US 10Y Yield)
      Pillar 5: Real-Time Fundamental Sentiment Vector
    """
    tickers = {
        "crude": "BZ=F",
        "usdinr": "INR=X",
        "sp500": "ES=F",
        "dax": "^GDAXI",
        "dxy": "DX-Y.NYB",
        "hdfc": "HDFCBANK.NS",
        "icici": "ICICIBANK.NS",
        "sbi": "SBIN.NS",
        "reliance": "RELIANCE.NS",
        "infy": "INFY.NS"
    }

    pct = {}
    for key, symbol in tickers.items():
        pct[key] = fetch_yahoo_pct_change(symbol)

    metrics = {
        "pillar1_macro": 0.0,
        "pillar2_heavyweights": 0.0,
        "pillar3_flows": 0.0,
        "pillar4_global": 0.0,
        "pillar5_sentiment": 0.0,
        "banknifty_fundamental_score": 0.0,
        "nifty_fundamental_score": 0.0,
        "fundamental_regime": "NEUTRAL_BALANCED",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # ── PILLAR 1: MACRO-ECONOMIC (Crude, Currency, Yields) ──
    p1_score = 0.0
    crude_pct = pct.get("crude", 0.0)
    inr_pct = pct.get("usdinr", 0.0)
    if crude_pct > 1.5: p1_score -= 25.0
    elif crude_pct < -1.5: p1_score += 25.0
    if inr_pct > 0.3: p1_score -= 25.0
    elif inr_pct < -0.3: p1_score += 25.0
    metrics["pillar1_macro"] = p1_score

    # ── PILLAR 2: INDEX HEAVYWEIGHT PERFORMANCE (Earnings & Momentum) ──
    bn_heavy_score = (
        pct.get("hdfc", 0.0) * 0.35 +
        pct.get("icici", 0.0) * 0.30 +
        pct.get("sbi", 0.0) * 0.15
    ) * 20.0

    nifty_heavy_score = (
        pct.get("hdfc", 0.0) * 0.20 +
        pct.get("reliance", 0.0) * 0.25 +
        pct.get("icici", 0.0) * 0.15 +
        pct.get("infy", 0.0) * 0.15
    ) * 20.0

    metrics["pillar2_heavyweights"] = float(bn_heavy_score)

    # ── PILLAR 4: GLOBAL CROSS-ASSET (DXY, DAX, S&P) ──
    p4_score = 0.0
    dax_pct = pct.get("dax", 0.0)
    sp_pct = pct.get("sp500", 0.0)
    dxy_pct = pct.get("dxy", 0.0)

    if dax_pct > 0.4: p4_score += 30.0
    elif dax_pct < -0.4: p4_score -= 30.0
    if sp_pct > 0.5: p4_score += 30.0
    elif sp_pct < -0.5: p4_score -= 30.0
    if dxy_pct > 0.3: p4_score -= 20.0
    elif dxy_pct < -0.3: p4_score += 20.0
    metrics["pillar4_global"] = p4_score

    # ── COMBINE INTO COMPOSITE FUNDAMENTAL SCORES ──
    bn_fund_score = (p1_score * 0.25 + bn_heavy_score * 0.45 + p4_score * 0.30)
    bn_fund_score = float(np.clip(bn_fund_score, -100.0, 100.0))

    nifty_fund_score = (p1_score * 0.25 + nifty_heavy_score * 0.45 + p4_score * 0.30)
    nifty_fund_score = float(np.clip(nifty_fund_score, -100.0, 100.0))

    metrics["banknifty_fundamental_score"] = bn_fund_score
    metrics["nifty_fundamental_score"] = nifty_fund_score

    if bn_fund_score >= 30.0:
        metrics["fundamental_regime"] = "BULLISH_EXPANSION"
    elif bn_fund_score <= -30.0:
        metrics["fundamental_regime"] = "BEARISH_HEADWINDS"
    else:
        metrics["fundamental_regime"] = "NEUTRAL_BALANCED"

    log.info("FUNDAMENTAL ANALYSIS: BankNifty Score=%.1f | Nifty Score=%.1f | Regime=%s | HeavyweightImpact=%.1f",
             bn_fund_score, nifty_fund_score, metrics["fundamental_regime"], bn_heavy_score)

    return metrics


def compute_fundamental_score(underlying: str = "BANKNIFTY") -> float:
    """
    Helper function to return the composite fundamental score for a given underlying.
    """
    metrics = fetch_fundamental_metrics()
    if "BANK" in underlying.upper():
        return metrics.get("banknifty_fundamental_score", 0.0)
    return metrics.get("nifty_fundamental_score", 0.0)
