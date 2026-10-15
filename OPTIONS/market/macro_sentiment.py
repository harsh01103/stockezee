"""
Global Macro Sentiment Layer.

Fetches real-time macro data from free sources (no API keys required):
  1. Crude Oil (Brent) — Yahoo Finance
  2. US Futures (S&P 500 / ES) — Yahoo Finance
  3. USD/INR — Yahoo Finance
  4. India VIX — NSE
  5. Global News Sentiment — Google News RSS keyword scan

Computes a composite Macro Risk Score (0.0 - 1.0) that feeds into
runner.py's signal generation pipeline to suppress or modify trades
based on global macro conditions.

Author: AI Agent (Antigravity)
Date: 2026-07-08
"""

import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

import httpx
from market.fundamental_analyzer import fetch_fundamental_metrics

log = logging.getLogger(__name__)

# ── Yahoo Finance Tickers ──────────────────────────────────────
CRUDE_OIL_TICKER = "BZ=F"       # Brent Crude Futures
SP500_FUTURES_TICKER = "ES=F"   # S&P 500 E-mini Futures
USDINR_TICKER = "INR=X"        # USD/INR
INDIA_VIX_TICKER = "^INDIAVIX" # India VIX

# ── Risk Thresholds ────────────────────────────────────────────
CRUDE_HIGH_RISK_PCT = 3.0       # >3% crude spike = high risk
CRUDE_MED_RISK_PCT = 1.5        # >1.5% = medium risk
VIX_HIGH_RISK_PCT = 20.0        # >20% VIX spike = high risk  
VIX_HIGH_LEVEL = 18.0           # Absolute VIX level threshold
VIX_MED_RISK_PCT = 10.0         # >10% VIX spike = medium risk
SP500_HIGH_RISK_PCT = -1.5      # S&P down >1.5% = high risk
SP500_MED_RISK_PCT = -0.8       # S&P down >0.8% = medium risk
USDINR_HIGH_RISK_PCT = 0.5      # Rupee depreciation >0.5% = high risk
USDINR_MED_RISK_PCT = 0.25      # >0.25% = medium risk

# ── News Sentiment Keywords (bearish signals) ─────────────────
BEARISH_KEYWORDS = [
    "war", "strike", "sanctions", "nuclear", "missile",
    "crude oil surge", "oil spike", "oil crisis",
    "recession", "crash", "sell-off", "selloff",
    "iran", "russia", "china taiwan", "north korea",
    "rate hike", "fed hawkish", "inflation surge",
    "bank crisis", "default", "debt crisis",
    "rupee crash", "rupee fall", "capital outflow",
    "fii selling", "foreign selling",
    "geopolitical", "escalation", "military",
    "trump tariff", "trade war",
]

# High-impact keywords get extra weight
HIGH_IMPACT_KEYWORDS = [
    "war", "nuclear", "missile", "sanctions",
    "crude oil surge", "oil crisis", "crash",
]

# ── Cache ──────────────────────────────────────────────────────
_macro_cache: Dict[str, Any] = {}
_macro_cache_ts: float = 0
MACRO_CACHE_TTL = 300  # 5 minutes


def _fetch_yahoo_quote(ticker: str, client: httpx.Client) -> Optional[Dict]:
    """Fetch quote data from Yahoo Finance v8 API (no key needed)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "range": "2d",
        "interval": "1d",
        "includePrePost": "true",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = client.get(url, params=params, headers=headers, timeout=8.0)
        if resp.status_code != 200:
            log.debug("Yahoo Finance %s returned %d", ticker, resp.status_code)
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        
        meta = result[0].get("meta", {})
        indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
        timestamps = result[0].get("timestamp", [])
        closes = indicators.get("close", [])
        
        current_price = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
        
        if current_price and prev_close and prev_close > 0:
            pct_change = ((current_price - prev_close) / prev_close) * 100
        else:
            pct_change = 0
            
        return {
            "ticker": ticker,
            "price": current_price,
            "prev_close": prev_close,
            "pct_change": round(pct_change, 2),
        }
    except Exception as e:
        log.debug("Yahoo Finance fetch error for %s: %s", ticker, e)
        return None


def _fetch_india_vix(client: httpx.Client) -> Optional[Dict]:
    """Fetch India VIX from Yahoo Finance."""
    return _fetch_yahoo_quote(INDIA_VIX_TICKER, client)


def _fetch_news_sentiment(client: httpx.Client) -> Dict:
    """
    Scan Google News RSS for bearish macro keywords.
    Returns a sentiment score and matched headlines.
    """
    feeds = [
        "https://news.google.com/rss/search?q=india+market+stock&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=crude+oil+price&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=nifty+sensex&hl=en-IN&gl=IN&ceid=IN:en",
    ]
    
    all_titles = []
    for feed_url in feeds:
        try:
            resp = client.get(feed_url, timeout=8.0, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.iter("item"):
                    title_el = item.find("title")
                    pub_date_el = item.find("pubDate")
                    if title_el is not None and title_el.text:
                        title = title_el.text.strip()
                        all_titles.append(title.lower())
        except Exception as e:
            log.debug("News RSS fetch error: %s", e)
    
    if not all_titles:
        return {"score": 0.0, "matched_headlines": [], "total_scanned": 0}
    
    matched = []
    high_impact_hits = 0
    normal_hits = 0
    
    for title in all_titles:
        for kw in BEARISH_KEYWORDS:
            if kw in title:
                matched.append(title[:100])
                if kw in HIGH_IMPACT_KEYWORDS:
                    high_impact_hits += 1
                else:
                    normal_hits += 1
                break  # don't double-count the same headline
    
    # Score: each high-impact hit = 0.15, normal hit = 0.05, capped at 1.0
    raw_score = (high_impact_hits * 0.15) + (normal_hits * 0.05)
    score = min(1.0, raw_score)
    
    return {
        "score": round(score, 3),
        "matched_headlines": matched[:10],  # top 10
        "total_scanned": len(all_titles),
        "high_impact_hits": high_impact_hits,
        "normal_hits": normal_hits,
    }


def fetch_macro_data() -> Dict[str, Any]:
    """
    Fetch all macro indicators and compute composite risk score.
    Returns a dict with individual scores and the final composite.
    
    This function is SAFE to call frequently — it caches for 5 minutes.
    """
    global _macro_cache, _macro_cache_ts
    
    now = time.time()
    if _macro_cache and (now - _macro_cache_ts) < MACRO_CACHE_TTL:
        return _macro_cache
    
    log.info("Fetching global macro sentiment data...")
    
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crude_oil": None,
        "sp500_futures": None,
        "usdinr": None,
        "india_vix": None,
        "news_sentiment": None,
        "banknifty_fundamental_score": 0.0,
        "nifty_fundamental_score": 0.0,
        "fundamental_regime": "NEUTRAL_BALANCED",
        "scores": {},
        "macro_risk_score": 0.0,
        "risk_level": "LOW",
        "regime_override": None,
        "position_size_multiplier": 1.0,
    }
    
    with httpx.Client() as client:
        # 1. Crude Oil
        crude = _fetch_yahoo_quote(CRUDE_OIL_TICKER, client)
        if crude:
            result["crude_oil"] = crude
            pct = crude["pct_change"]
            if pct >= CRUDE_HIGH_RISK_PCT:
                result["scores"]["crude"] = 1.0
            elif pct >= CRUDE_MED_RISK_PCT:
                result["scores"]["crude"] = 0.5
            elif pct > 0:
                result["scores"]["crude"] = pct / CRUDE_HIGH_RISK_PCT * 0.3
            else:
                result["scores"]["crude"] = 0.0
            log.info("MACRO_CRUDE: $%.2f (%.2f%%)", crude["price"], pct)
        
        # 2. S&P 500 Futures
        sp500 = _fetch_yahoo_quote(SP500_FUTURES_TICKER, client)
        if sp500:
            result["sp500_futures"] = sp500
            pct = sp500["pct_change"]
            if pct <= SP500_HIGH_RISK_PCT:
                result["scores"]["sp500"] = 1.0
            elif pct <= SP500_MED_RISK_PCT:
                result["scores"]["sp500"] = 0.5
            elif pct < 0:
                result["scores"]["sp500"] = abs(pct) / abs(SP500_HIGH_RISK_PCT) * 0.3
            else:
                result["scores"]["sp500"] = 0.0
            log.info("MACRO_SP500: %.2f (%.2f%%)", sp500["price"], pct)
        
        # 3. USD/INR
        usdinr = _fetch_yahoo_quote(USDINR_TICKER, client)
        if usdinr:
            result["usdinr"] = usdinr
            # For USD/INR, a positive change means rupee depreciation = bearish
            pct = usdinr["pct_change"]
            if pct >= USDINR_HIGH_RISK_PCT:
                result["scores"]["usdinr"] = 1.0
            elif pct >= USDINR_MED_RISK_PCT:
                result["scores"]["usdinr"] = 0.5
            elif pct > 0:
                result["scores"]["usdinr"] = pct / USDINR_HIGH_RISK_PCT * 0.3
            else:
                result["scores"]["usdinr"] = 0.0
            log.info("MACRO_USDINR: %.4f (%.2f%%)", usdinr["price"], pct)
        
        # 4. India VIX
        vix = _fetch_india_vix(client)
        if vix:
            result["india_vix"] = vix
            pct = vix["pct_change"]
            level = vix["price"]
            # Both absolute level AND spike matter
            vix_score = 0.0
            if pct >= VIX_HIGH_RISK_PCT:
                vix_score = max(vix_score, 1.0)
            elif pct >= VIX_MED_RISK_PCT:
                vix_score = max(vix_score, 0.5)
            if level >= VIX_HIGH_LEVEL:
                vix_score = max(vix_score, 0.7)
            result["scores"]["vix"] = vix_score
            log.info("MACRO_VIX: %.2f (%.2f%% change)", level, pct)
        
        # 5. European Market (DAX / Europe Open Tracker)
        dax = _fetch_yahoo_quote("^GDAXI", client)
        if dax:
            result["dax"] = dax
            pct = dax["pct_change"]
            if pct <= -0.4:
                result["euro_sentiment"] = "BEARISH"
            elif pct >= 0.4:
                result["euro_sentiment"] = "BULLISH"
            else:
                result["euro_sentiment"] = "NEUTRAL"
            result["euro_pct_change"] = pct
            log.info("MACRO_EURO_DAX: %.2f (%.2f%%) -> euro_sentiment=%s", dax["price"], pct, result["euro_sentiment"])
        else:
            result["euro_sentiment"] = "NEUTRAL"
            result["euro_pct_change"] = 0.0
        # news = _fetch_news_sentiment(client)
        # result["news_sentiment"] = news
        # result["scores"]["news"] = news["score"]
        # if news["matched_headlines"]:
        #     log.info("MACRO_NEWS: %d bearish headlines (score=%.2f)", 
        #              len(news["matched_headlines"]), news["score"])
    
    # ── Compute Composite Risk Score ─────────────────────────────
    # Weighted average: crude(35%) + vix(30%) + sp500(25%) + usdinr(10%)
    weights = {
        "crude": 0.35,
        "vix": 0.30,
        "sp500": 0.25,
        "usdinr": 0.10,
    }
    
    total_weight = 0
    weighted_sum = 0
    for key, weight in weights.items():
        if key in result["scores"]:
            weighted_sum += result["scores"][key] * weight
            total_weight += weight
    
    if total_weight > 0:
        composite = weighted_sum / total_weight
    else:
        composite = 0.0
    
    result["macro_risk_score"] = round(composite, 4)
    
    # ── Determine Risk Level and Regime Override ─────────────────
    if composite >= 0.7:
        result["risk_level"] = "HIGH"
        result["regime_override"] = "BEARISH_ONLY"
        result["position_size_multiplier"] = 0.5
        result["confidence_boost"] = 0.10  # require +10% higher confidence for any trade
    elif composite >= 0.4:
        result["risk_level"] = "ELEVATED"
        result["regime_override"] = None  # no full override, but tighten
        result["position_size_multiplier"] = 0.75
        result["confidence_boost"] = 0.05  # require +5% higher confidence
    else:
        result["risk_level"] = "LOW"
        result["regime_override"] = None
        result["position_size_multiplier"] = 1.0
        result["confidence_boost"] = 0.0
    
    log.info(
        "MACRO COMPOSITE: %.3f (%s) | crude=%.2f vix=%.2f sp500=%.2f usdinr=%.2f",
        composite, result["risk_level"],
        result["scores"].get("crude", 0),
        result["scores"].get("vix", 0),
        result["scores"].get("sp500", 0),
        result["scores"].get("usdinr", 0),
    )
    
    # ── 5-PILLAR FUNDAMENTAL ANALYSIS ENGINE INTEGRATION ──
    try:
        fund = fetch_fundamental_metrics()
        result["banknifty_fundamental_score"] = fund.get("banknifty_fundamental_score", 0.0)
        result["nifty_fundamental_score"] = fund.get("nifty_fundamental_score", 0.0)
        result["fundamental_regime"] = fund.get("fundamental_regime", "NEUTRAL_BALANCED")
    except Exception as e:
        log.warning("Fundamental metrics integration error: %s", e)

    # Cache the result
    _macro_cache = result
    _macro_cache_ts = now
    
    return result


def format_macro_telegram_alert(macro: Dict) -> str:
    """Format macro data for Telegram alert."""
    crude = macro.get("crude_oil", {}) or {}
    sp500 = macro.get("sp500_futures", {}) or {}
    usdinr = macro.get("usdinr", {}) or {}
    vix = macro.get("india_vix", {}) or {}
    news = macro.get("news_sentiment", {}) or {}
    
    risk_emoji = {"LOW": "🟢", "ELEVATED": "🟡", "HIGH": "🔴"}.get(macro["risk_level"], "⚪")
    
    lines = [
        f"{risk_emoji} *MACRO RISK: {macro['risk_level']}* (Score: {macro['macro_risk_score']:.2f})",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    if crude:
        emoji = "🔴" if crude["pct_change"] >= CRUDE_MED_RISK_PCT else "🟢"
        lines.append(f"🛢️ Crude: ${crude['price']:.2f} ({emoji} {crude['pct_change']:+.2f}%)")
    
    if vix:
        emoji = "🔴" if vix["pct_change"] >= VIX_MED_RISK_PCT else "🟢"
        lines.append(f"📊 India VIX: {vix['price']:.2f} ({emoji} {vix['pct_change']:+.2f}%)")
    
    if sp500:
        emoji = "🔴" if sp500["pct_change"] <= SP500_MED_RISK_PCT else "🟢"
        lines.append(f"🇺🇸 S&P 500: {sp500['price']:.2f} ({emoji} {sp500['pct_change']:+.2f}%)")
    
    if usdinr:
        emoji = "🔴" if usdinr["pct_change"] >= USDINR_MED_RISK_PCT else "🟢"
        lines.append(f"💱 USD/INR: {usdinr['price']:.4f} ({emoji} {usdinr['pct_change']:+.2f}%)")
    
    if news and news.get("matched_headlines"):
        lines.append(f"📰 Bearish News: {len(news['matched_headlines'])} headlines")
        for h in news["matched_headlines"][:3]:
            lines.append(f"  • _{h[:80]}_")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    
    if macro["risk_level"] == "HIGH":
        lines.append("⚠️ *DEFENSIVE MODE*: Only PE/bearish trades allowed")
        lines.append(f"📉 Position size: {int(macro['position_size_multiplier']*100)}%")
    elif macro["risk_level"] == "ELEVATED":
        lines.append(f"⚡ Confidence boost: +{macro.get('confidence_boost',0)*100:.0f}%")
        lines.append(f"📉 Position size: {int(macro['position_size_multiplier']*100)}%")
    
    return "\n".join(lines)


def invalidate_cache():
    """Force a fresh macro data fetch on next call."""
    global _macro_cache_ts
    _macro_cache_ts = 0


# ── Standalone test ────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    data = fetch_macro_data()
    
    print("\n" + "=" * 60)
    print("GLOBAL MACRO SENTIMENT REPORT")
    print("=" * 60)
    print(f"\nComposite Risk Score: {data['macro_risk_score']:.3f}")
    print(f"Risk Level: {data['risk_level']}")
    print(f"Regime Override: {data.get('regime_override', 'None')}")
    print(f"Position Size: {data['position_size_multiplier']*100:.0f}%")
    print(f"Confidence Boost: +{data.get('confidence_boost', 0)*100:.0f}%")
    
    print("\nIndividual Scores:")
    for k, v in data["scores"].items():
        print(f"  {k}: {v:.3f}")
    
    if data.get("crude_oil"):
        print(f"\nCrude Oil: ${data['crude_oil']['price']:.2f} ({data['crude_oil']['pct_change']:+.2f}%)")
    if data.get("india_vix"):
        print(f"India VIX: {data['india_vix']['price']:.2f} ({data['india_vix']['pct_change']:+.2f}%)")
    if data.get("sp500_futures"):
        print(f"S&P 500: {data['sp500_futures']['price']:.2f} ({data['sp500_futures']['pct_change']:+.2f}%)")
    if data.get("usdinr"):
        print(f"USD/INR: {data['usdinr']['price']:.4f} ({data['usdinr']['pct_change']:+.2f}%)")
    
    if data.get("news_sentiment", {}).get("matched_headlines"):
        print(f"\nBearish Headlines ({len(data['news_sentiment']['matched_headlines'])}):")
        for h in data["news_sentiment"]["matched_headlines"]:
            print(f"  - {h}")
    
    print("\n" + format_macro_telegram_alert(data))
