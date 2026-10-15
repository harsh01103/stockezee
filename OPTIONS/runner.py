"""
PHASE O3A — AUTO EXECUTION PIPELINE (TIME-BOUND)
Watches for new parquet flushes and automatically generates
time-bound trade signals with executable timing.
"""
# pyrefly: ignore [missing-import]
import glob, os, csv, time, polars as pl, numpy as np, logging, httpx, threading, math, uuid, json
from datetime import datetime, date, timedelta
from pathlib import Path
# pyrefly: ignore [missing-import]
from numba import njit

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from research.chart_signals import compute_chart_signals
from opportunities.scorer import (
    score_momentum_opportunities,
    score_mean_reversion_opportunities,
    score_closing_auction_opportunities,
    score_expiry_gamma_opportunities,
)
from opportunities.universe import (
    build_momentum_universe,
    build_mean_reversion_universe,
    build_closing_auction_universe,
)
from opportunities.ranker import rank_opportunities
from opportunities.confidence import (
    calculate_strategy_confidence,
)
from auth.auth_manager import AuthManager
from trade.executor import UpstoxExecutor

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

# Initialize Upstox Executor for zero-latency Python execution
auth_manager = AuthManager()
global_executor = UpstoxExecutor(auth_manager)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("runner")
logging.getLogger("universe").setLevel(logging.WARNING)

# Config
DATE_STR = date.today().strftime("%Y-%m-%d")
RAW_DIR = Path(f"data/raw/{DATE_STR}")
OUTPUT_CSV = Path("reports/live_trade_ideas.csv")
ARCHIVE_CSV = Path("reports/live_trade_archive.csv")
PUBLISH_THRESHOLD = 0.70
POLL_INTERVAL_SEC = 3

# ── Execution cost filters ────────────────────────────────────
MIN_PREMIUM = 25          # Rs. — reject LTP below this
MAX_SPREAD_PCT = 1.0      # % — reject if (ask-bid)/mid > this
MIN_VOLUME = 5000         # lots — reject illiquid contracts
LOT_SIZE = {"NIFTY": 65, "BANKNIFTY": 30}
ROUND_TRIP_COST = 50      # Rs. approx brokerage+STT+GST per lot
MAX_CONFIDENCE = 0.99     # Structural math allows up to 0.95; no longer penalized for being "too good"
PE_MIN_CONFIDENCE = 0.75  # Asymmetric penalty for puts
MAX_BUDGET = 45_000       # Rs. — max capital per trade (scaled for ~3 lots on 1L account)
MAX_BANKNIFTY_PREMIUM = 1600 # Allow Deep ITM options and 30-DTE Monthly ATMs
ROLLING_CONTEXT_MINUTES = 15  # 15 mins is sufficient for all short-term momentum rolling features

# ── MASTER FIX: Hard Scalping Logic ───────────────────────────
# Scaled for 1L Principal (~45% Annual Target ROI)
SCALP_TARGET_RS = 1800   # Hard Take-Profit per trade (Rs. 1800) -> 1.2x R/R Profile
SCALP_STOP_RS = 1500     # Hard Stop-Loss per trade (Rs. 1500) -> 1.5% max risk per trade
DAILY_MAX_LOSS = -2500   # Daily circuit breaker (2.5% max drawdown per day)
MAX_MOMENTUM_PREMIUM = {"NIFTY": 600, "BANKNIFTY": 1600}  # Allow ATM options — OTM loses money

# ── Telemetry ─────────────────────────────────────────────────
TELEMETRY_VERSION = "2.2"

# ── Quality gates (data-driven from 43 live trades) ──────────
MAX_SLIPPAGE_PCT = 0.05   # % — reject if execution gap > this

# ── Scoring weights (mirrored from run_pipeline for telemetry) ─
SCORE_WEIGHTS = {
    "s_vwap": 0.35,          # Structural trend: Price vs VWAP
    "s_oi_flow": 0.35,       # Institutional flow: dPCR/dt direction
    "s_momentum": 0.30,      # Short-term momentum: EMA cross or price velocity
}

# ── Telegram Alerts ───────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8801890087:AAEEICbN0GvLSj4ZTnUPSESNcIusPvXJYPs"
TELEGRAM_CHAT_ID = "5661148030"

# State
seen_files = set()
published_contracts = set()  # dedup key: (underlying, expiry, strike, option_type)
all_signals = []
flush_latencies = []
latest_spot_adx = 0.0
# Legacy global removed
nse_lock = threading.Lock()  # protect cache from concurrent access

# ── Global Macro Sentiment ─────────────────────────────────────
macro_cached_data = {}  # cached result from macro_sentiment.fetch_macro_data()
macro_last_refresh = 0  # epoch timestamp of last refresh
MACRO_REFRESH_INTERVAL = 1800  # refresh every 30 minutes

# ── Adaptive Alpha Engine v2: Self-Awareness State ─────────────
consecutive_losses = 0           # ALC: tracks consecutive losing trades
cooldown_until = None            # ALC: datetime when cooldown expires
last_directions = []             # SDT: last N published signal directions ("CE"/"PE")
direction_cooldown_until = None  # SDT: datetime when direction cooldown expires
ALC_COOLDOWN_MINUTES = 10        # ALC: pause duration after 2 consecutive losses
ALC_RESUME_MIN_CONF = 0.60       # ALC: minimum confidence to resume after cooldown (adjusted for pure confidence)
SDT_MAX_SAME_SIDE = 3            # SDT: max consecutive same-direction trades
SDT_COOLDOWN_MINUTES = 15        # SDT: pause duration after same-direction throttle
RCG_CAUTION_THRESHOLD = -1500    # RCG: daily PnL threshold for caution mode
RCG_DEFENSIVE_THRESHOLD = -3000  # RCG: daily PnL threshold for defensive mode
RCG_CAUTION_MIN_CONF = 0.60      # RCG: min confidence in caution mode
RCG_DEFENSIVE_MIN_CONF = 0.65    # RCG: min confidence in defensive mode

# ── Regime Hysteresis State ─────────────
current_regimes = {}
latest_spot_directions = {}
cached_ib_high = {}
cached_ib_low = {}
regime_state = {"whipsaw_penalty": 0, "whipsaw_decay_until": 0}
_last_idea_logged_time = {}

# ── Dynamic Telegram Bot State ─────────────
def get_dynamic_max_loss():
    try:
        if Path("config/maxloss.json").exists():
            with open("config/maxloss.json", "r") as f:
                data = json.load(f)
                return data.get("amount", DAILY_MAX_LOSS)
    except: pass
    return DAILY_MAX_LOSS

def get_blocked_symbols():
    try:
        if Path("config/block.json").exists():
            with open("config/block.json", "r") as f:
                return json.load(f)
    except: pass
    return []

def get_trail_overrides():
    try:
        if Path("config/trail_overrides.json").exists():
            with open("config/trail_overrides.json", "r") as f:
                return json.load(f)
    except: pass
    return {}

def export_telemetry(df_res):
    if df_res is None or df_res.is_empty(): return
    try:
        Path("config").mkdir(exist_ok=True)
        active_strats = []
        if any("MOMENTUM" in r for r in current_regimes.values()):
            active_strats.append("Momentum")
        if any("MEAN_REVERSION" in r for r in current_regimes.values()):
            active_strats.append("Mean Reversion")
        active_strats.append("CAS")
        
        tele = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "active_engines": ", ".join(active_strats)}
        for u in df_res["underlying"].unique():
            df_u = df_res.filter(pl.col("underlying") == u)
            if df_u.is_empty(): continue
            latest_ts = df_u["timestamp"].max()
            df_latest = df_u.filter(pl.col("timestamp") == latest_ts)
            
            oi_net = 0
            if "oi" in df_u.columns and "option_type" in df_u.columns:
                sort_col = "real_timestamp" if "real_timestamp" in df_u.columns else "timestamp"
                df_chain = df_u.sort(sort_col).unique(subset=["strike", "option_type"], keep="last")
                pe_oi = df_chain.filter(pl.col("option_type") == "PE")["oi"].sum()
                ce_oi = df_chain.filter(pl.col("option_type") == "CE")["oi"].sum()
                if pe_oi + ce_oi > 0: oi_net = round((pe_oi - ce_oi) / (pe_oi + ce_oi) * 100, 1)
            
            ce_prem, pe_prem, atm_strike = 0, 0, 0
            if "spot" in df_latest.columns and "strike" in df_latest.columns:
                spot = df_latest["spot"].mean()
                if spot:
                    atm_strike = round(spot / 50) * 50 if u == "NIFTY" else round(spot / 100) * 100
                    atm_ce = df_latest.filter((pl.col("strike") == atm_strike) & (pl.col("option_type") == "CE"))
                    atm_pe = df_latest.filter((pl.col("strike") == atm_strike) & (pl.col("option_type") == "PE"))
                    ce_prem = round(atm_ce["ltp"].mean(), 1) if not atm_ce.is_empty() and "ltp" in atm_ce.columns else 0
                    pe_prem = round(atm_pe["ltp"].mean(), 1) if not atm_pe.is_empty() and "ltp" in atm_pe.columns else 0
                    
            tele[u] = {
                "regime": current_regimes.get(u, "UNKNOWN"),
                "oi_net": oi_net,
                "atm_strike": atm_strike,
                "ce_prem": ce_prem,
                "pe_prem": pe_prem
            }
        with open("config/telemetry.json", "w") as f:
            json.dump(tele, f)
    except Exception as e: 
        log.error("Telemetry export failed: %s", e)

def get_parquet_files():
    """Get sorted list of parquet files in today's raw directory chronologically."""
    if not RAW_DIR.exists():
        return []
    # FIX: Sort by modification time to prevent random alphabetical hashing delays
    return sorted(RAW_DIR.glob("*.parquet"), key=lambda f: f.stat().st_mtime)


def wait_for_new_parquet():
    """Block until a new parquet file appears. Returns list of new files."""
    while True:
        current_files = set(get_parquet_files())
        new_files = current_files - seen_files
        if new_files:
            return sorted(list(new_files), key=lambda f: f.stat().st_mtime)
        time.sleep(POLL_INTERVAL_SEC)


def load_rolling_context():
    """Load all parquet files within the rolling context window."""
    files = get_parquet_files()
    if not files:
        return pl.DataFrame()
    
    dfs = []
    for f in files:
        try:
            df = pl.read_parquet(f).with_columns(
                pl.lit(os.path.basename(str(f))).alias("source_file")
            )
            dfs.append(df)
        except Exception as e:
            log.warning("Failed to read %s: %s", f, e)
    
    if not dfs:
        return pl.DataFrame()
    
    df = pl.concat(dfs, how="diagonal_relaxed")
    
    # Trim to rolling context window
    if "timestamp" in df.columns:
        cutoff = time.time() * 1000 - ROLLING_CONTEXT_MINUTES * 60 * 1000
        df = df.filter(pl.col("timestamp") >= cutoff)
    
    return df


def fetch_upstox_intraday_ib(underlying: str):
    """
    Fallback: Fetches 1-minute intraday index candles from Upstox REST API 
    if recorder was started late and missing 9:15-10:15 AM spot data.
    """
    import urllib.request, json
    key_map = {"NIFTY": "NSE_INDEX%7CNifty%2050", "BANKNIFTY": "NSE_INDEX%7CNifty%20Bank"}
    key = key_map.get(underlying)
    if not key:
        return 0.0, 0.0
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{key}/1minute"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candles = data.get("data", {}).get("candles", [])
            # Candles: [timestamp, open, high, low, close, volume, oi]
            # Filter for 9:15 to 10:15 IST
            ib_highs = []
            ib_lows = []
            for c in candles:
                ts_str = str(c[0])  # e.g. "2026-07-30T09:15:00+05:30"
                if "T09:" in ts_str or "T10:0" in ts_str or "T10:10" in ts_str or "T10:15" in ts_str:
                    ib_highs.append(float(c[2]))
                    ib_lows.append(float(c[3]))
            if ib_highs and ib_lows:
                log.info("REST FALLBACK IB [%s]: High=%.2f, Low=%.2f (fetched %d 1-min candles from Upstox REST API)", 
                         underlying, max(ib_highs), min(ib_lows), len(ib_highs))
                return float(max(ib_highs)), float(min(ib_lows))
    except Exception as e:
        log.warning("Failed to fetch Upstox intraday IB fallback for %s: %s", underlying, e)
    return 0.0, 0.0


def run_pipeline(df_raw, date_str=None, dry_run=False):
    """Run full pipeline: features -> research -> chart -> NSE -> score."""
    t0 = time.time()
    
    # Features
    target_date = date_str or DATE_STR
    res = process_features(df_raw, target_date, dry_run=dry_run)
    df_feat = res["df_features"]
    
    if df_feat.is_empty():
        return pl.DataFrame(), 0, "NO_DATA"
    
    # ── Timestamp alignment ──────────────────────────────────────────
    if "timestamp" in df_feat.columns:
        BUCKET_MS = 60_000  # 1-minute buckets
        df_feat = df_feat.with_columns(
            pl.col("timestamp").alias("real_timestamp"),
            (pl.col("timestamp") // BUCKET_MS * BUCKET_MS).cast(pl.Int64).alias("timestamp")
        )
        pk_dedup = ["timestamp", "underlying", "expiry", "strike", "option_type"]
        available_pk = [c for c in pk_dedup if c in df_feat.columns]
        
        # Sort by the primary keys, then real_timestamp, so keep='last' correctly picks the freshest microsecond tick
        sort_keys = available_pk + ["real_timestamp"] if "real_timestamp" in df_feat.columns else available_pk
        df_feat = df_feat.sort(sort_keys)
        df_feat = df_feat.unique(subset=available_pk, keep="last")
    
    # ── Layer 0: Research enrichment ─────────────────────────────────
    df_res = compute_gex_proxy(
        compute_regime_features(
            compute_vwoim(
                compute_oi_flow(df_feat)
            )
        )
    )
    df_res = df_res.sort("timestamp")
    
    # ── Layer 1: Chart Analysis ──────────────────────────────────────
    df_res = compute_chart_signals(df_res)
    
    # ── Layer 3: Black-Scholes Live Greeks ───────────────────────────
    df_res = add_live_greeks(df_res)
            
    # ── MASTER REGIME SWITCHER (FIX #6: use SPOT price, not option means) ──
    if df_res.is_empty():
        return pl.DataFrame(), 0, "NONE"
        
    underlyings = df_res["underlying"].unique().to_list()
    
    global current_regimes
    global latest_spot_directions
    
    all_confs = []
    regimes_detected = []
    
    for u in underlyings:
        df_u = df_res.filter(pl.col("underlying") == u)
        if df_u.is_empty(): continue
        
        latest_ts = df_u["timestamp"].max()
        df_u_latest = df_u.filter(pl.col("timestamp") == latest_ts)
        
        spot = 0
        vwap_val = 0
        ib_high = 0
        ib_low = 0
        oi_net = 0
        
        if "spot" in df_u.columns:
            spot = float(df_u_latest["spot"].mean()) if not df_u_latest.is_empty() else 0
            raw_ibh = df_u_latest["ib_high"].drop_nulls() if not df_u_latest.is_empty() and "ib_high" in df_u_latest.columns else []
            raw_ibl = df_u_latest["ib_low"].drop_nulls() if not df_u_latest.is_empty() and "ib_low" in df_u_latest.columns else []
            if len(raw_ibh) > 0 and len(raw_ibl) > 0:
                ib_high = float(raw_ibh.mean())
                ib_low = float(raw_ibl.mean())
                cached_ib_high[u] = ib_high
                cached_ib_low[u] = ib_low
            else:
                if u not in cached_ib_high or cached_ib_high[u] == 0:
                    api_h, api_l = fetch_upstox_intraday_ib(u)
                    if api_h > 0 and api_l > 0:
                        cached_ib_high[u] = api_h
                        cached_ib_low[u] = api_l
                ib_high = cached_ib_high.get(u, 0)
                ib_low = cached_ib_low.get(u, 0)
            vwap_val = float(df_u_latest["vwap"].mean()) if not df_u_latest.is_empty() and "vwap" in df_u_latest.columns and df_u_latest["vwap"][0] is not None else spot
            
            if "oi" in df_u.columns and "option_type" in df_u.columns:
                # We must use the latest state of ALL strikes, not just the single option that ticked at latest_ts
                sort_col = "real_timestamp" if "real_timestamp" in df_u.columns else "timestamp"
                df_chain = df_u.sort(sort_col).unique(subset=["strike", "option_type"], keep="last")
                pe_oi = df_chain.filter(pl.col("option_type") == "PE")["oi"].sum()
                ce_oi = df_chain.filter(pl.col("option_type") == "CE")["oi"].sum()
                total_oi = pe_oi + ce_oi
                if total_oi > 0:
                    oi_ratio = (pe_oi - ce_oi) / total_oi
                    # Scale to 100 to represent absolute percentage skew of institutional capital
                    oi_net = oi_ratio * 100.0
                
            # Direction Logic
            spot_dir = "NEUTRAL"
            if oi_net <= -3.0:
                spot_dir = "BEARISH"
            elif oi_net >= 3.0:
                spot_dir = "BULLISH"
            else:
                if spot < vwap_val:
                    spot_dir = "BEARISH"
                else:
                    spot_dir = "BULLISH"
            latest_spot_directions[u] = spot_dir
        else:
            latest_spot_directions[u] = "NEUTRAL"
            
        # Regime Switching
        current_regime = current_regimes.get(u, "CHOPPY_MEAN_REVERSION")
        
        # 0. VIX Panic Override
        is_vix_panic = False
        if macro_cached_data and macro_cached_data.get("india_vix"):
            vix_pct = macro_cached_data["india_vix"].get("pct_change", 0.0)
            if vix_pct > 3.0 and latest_spot_directions.get(u, "NEUTRAL") == "BEARISH":
                current_regime = "PANIC_BEAR"
                is_vix_panic = True
            elif vix_pct > 3.0 and latest_spot_directions.get(u, "NEUTRAL") == "BULLISH":
                current_regime = "PANIC_BULL"  # Upside short-squeeze (Vol surge + Spot surge)
                is_vix_panic = True
                
        # Choppy Price Action Detection (VWAP Crosses)
        thirty_mins_ms = 30 * 60 * 1000
        cutoff_ts = latest_ts - thirty_mins_ms
        df_recent = df_u.filter(pl.col("timestamp") >= cutoff_ts)
        
        is_choppy_price_action = False
        if not df_recent.is_empty() and "spot" in df_recent.columns and "vwap" in df_recent.columns:
            sort_col = "real_timestamp" if "real_timestamp" in df_recent.columns else "timestamp"
            df_unique = df_recent.sort(sort_col).unique(subset=["timestamp"], keep="last")
            spots = df_unique["spot"].to_list()
            vwaps = df_unique["vwap"].to_list()
            
            crosses = 0
            if len(spots) > 2:
                positions = [1 if s > v else -1 for s, v in zip(spots, vwaps) if s is not None and v is not None]
                for i in range(1, len(positions)):
                    if positions[i] != positions[i-1]:
                        crosses += 1
            if crosses >= 3:
                is_choppy_price_action = True
        
        # IB Block
        inside_ib = False
        if not is_vix_panic and ib_high > 0 and ib_low > 0:
            if ib_low <= spot <= ib_high:
                inside_ib = True
                
        # A strongly trending market usually exhibits a 5%+ absolute skew in total Open Interest
        # However, if price broke out of the Initial Balance, we accept a 2%+ skew as confirmation
        required_skew = 5.0 if inside_ib else 2.0
        
        is_strong_trend = (abs(oi_net) >= required_skew) and (
            (oi_net > 0 and spot > vwap_val) or 
            (oi_net < 0 and spot < vwap_val) or
            abs(oi_net) >= 4.0
        )
        is_weak_trend = abs(oi_net) < 1.0
        
        # FIX: Strong institutional skew (>= 4%) should OVERRIDE choppiness.
        # Fading a clear trend (e.g. -5.9%) because of a few brief VWAP crosses is mathematically unsound.
        if is_choppy_price_action and abs(oi_net) >= 4.0:
            is_choppy_price_action = False
            log.info("[%s] Strong institutional skew (%.2f%%) overrides choppy price action.", u, oi_net)
        
        if current_regime == "CHOPPY_MEAN_REVERSION":
            if is_strong_trend and not is_choppy_price_action:
                current_regime = "TRENDING_MOMENTUM"
        else:
            if is_weak_trend or is_choppy_price_action:
                current_regime = "CHOPPY_MEAN_REVERSION"
                
        # Safety net: If price falls back into the IB, ensure it has the 5.0% skew to stay in trend mode
        if inside_ib and abs(oi_net) < 5.0:
            current_regime = "CHOPPY_MEAN_REVERSION"
            
        # ── DOJI / COMPRESSION FILTER ──
        # If the day's high-low range is extremely tight, it's a compression day, not a trend day.
        # Nifty < 0.4% range, BankNifty < 0.5% range
        df_raw_u = df_raw.filter(pl.col("underlying") == u)
        if not df_raw_u.is_empty() and "spot" in df_raw_u.columns:
            spots = df_raw_u["spot"].drop_nulls()
            if len(spots) > 0:
                day_high = spots.max()
                day_low = spots.min()
                if day_high > 0 and day_low > 0:
                    day_range_pct = (day_high - day_low) / day_low * 100
                    min_range_pct = 0.4 if u == "NIFTY" else 0.5
                    # FIX: Do not override a strong institutional trend (OI skew >= 4%) with a Doji filter.
                    if day_range_pct < min_range_pct and abs(oi_net) < 4.0:
                        if current_regime == "TRENDING_MOMENTUM":
                            log.info("[%s] MACRO REGIME OVERRIDE: Doji/Compression Day detected (range %.2f%% < %.2f%%) -> CHOPPY_MEAN_REVERSION", u, day_range_pct, min_range_pct)
                        current_regime = "CHOPPY_MEAN_REVERSION"

                
        current_regimes[u] = current_regime
        regimes_detected.append(f"{u}:{current_regime}")
        
        log.info("[%s] MACRO REGIME DETECTED: %s | IB Block: %s | OI Net: %.3f | Spot vs VWAP: %.1f", 
                 u, current_regime, inside_ib, oi_net, spot - vwap_val)
                 
        if current_regime in ("TRENDING_MOMENTUM", "TRENDING_BEAR"):
            log.info("[%s] Regime is %s -> Running Momentum Engine (Strategy A)", u, current_regime)
            df_conf = run_momentum_engine(df_u, t0, date_str, dry_run, macro_oi_net=oi_net)
        else:
            log.info("[%s] Regime is %s -> Running Mean Reversion Engine (Strategy B)", u, current_regime)
            df_conf = run_mean_reversion_engine(df_u, t0, latest_spot_directions[u], macro_oi_net=oi_net)
            
        if df_conf is not None and not df_conf.is_empty():
            all_confs.append(df_conf)
        
        # ── STRATEGY C & D: CLOSING AUCTION (3:15-3:35 PM) & EXPIRY POWER HOUR (2:45-3:35 PM) ──
        if latest_ts > 0:
            now_time = datetime.fromtimestamp(latest_ts / 1000.0)
        else:
            now_time = datetime.now()
            
        force_cas = False
        if Path("config/force_cas.flag").exists():
            force_cas = True
            try: Path("config/force_cas.flag").unlink()
            except: pass
            
        is_closing_window = (now_time.hour == 14 and now_time.minute >= 30) or \
                            (now_time.hour == 15 and now_time.minute <= 35) or force_cas
        
        if is_closing_window and spot > 0 and vwap_val > 0:
            today_str = now_time.strftime("%Y-%m-%d")
            expiries_in_data = df_u["expiry"].unique().to_list() if "expiry" in df_u.columns else []
            is_expiry_day = any(str(exp) == today_str for exp in expiries_in_data)
            is_trend_day = current_regime in ("TRENDING_BULL", "TRENDING_MOMENTUM", "TRENDING_BEAR", "PANIC_BEAR", "PANIC_BULL")
            
            # STRATEGY D: Expiry Power Hour Gamma Engine (Expiry Days 2:45 - 3:35 PM)
            if is_expiry_day and not force_cas:
                log.info("[%s] 🧨 STRATEGY D ACTIVE: Expiry Power Hour Gamma Engine (%s)", u, now_time.strftime("%H:%M"))
                df_expiry_today = df_u.filter(pl.col("expiry").cast(pl.Utf8) == today_str)
                df_power = run_power_hour_engine(df_expiry_today, t0, spot, vwap_val, oi_net, u)
                if df_power is not None and not df_power.is_empty():
                    log.info("[%s] 🚀 STRATEGY D EXPIRY GAMMA ENGINE TAKING 100%% PRIORITY LEAD!", u)
                    all_confs = [df_power]
            
            # STRATEGY C (Daily Closing Auction) has been disabled.
            # Its scoring mechanism relied on deprecated z-score features and acted 
            # as a blind market-order generator. On non-expiry days, we now rely
            # entirely on the Momentum Engine (with its late-day safety penalty).
            
    if all_confs:
        final_df = pl.concat(all_confs, how="diagonal_relaxed")
        if "composite_alpha_score" in final_df.columns:
            final_df = final_df.sort("composite_alpha_score", descending=True)
    else:
        final_df = pl.DataFrame()
        
    # Export telemetry for Telegram Bot
    export_telemetry(df_res)
        
    elapsed = round(time.time() - t0, 2)
    return final_df, elapsed, " | ".join(regimes_detected)


def run_momentum_engine(df_res, t0, date_str=None, dry_run=False, macro_oi_net=0.0):
    """
    Strategy A: High-Conviction Momentum Breakouts
    Looks for explosive acceleration in price, volume, and OI.
    Requires TRENDING_MOMENTUM macro regime.
    """
    if df_res.is_empty():
        return pl.DataFrame()
        
    # FIX #7: We need a minimum number of strikes to form a mathematical bell curve
    unique_strikes = df_res["strike"].n_unique()
    if unique_strikes < 5:
        log.warning("low_density=True  unique_strikes=%d  skipping momentum engine", unique_strikes)
        return pl.DataFrame()
        
    # Trim deep OTM/ITM junk to prevent them from skewing the Z-scores
    if "delta" in df_res.columns:
        df_filtered = df_res.filter(
            (pl.col("volume") > 500) & 
            (pl.col("delta").abs() >= 0.40) & 
            (pl.col("delta").abs() <= 0.85) &
            (((pl.col("ask") - pl.col("bid")) / ((pl.col("bid") + pl.col("ask")) / 2)) <= 0.025)
        )
        if df_filtered.height < 10:
            df_filtered = df_res.filter(
                (pl.col("volume") > 100) &
                (pl.col("delta").abs() >= 0.35) & 
                (pl.col("delta").abs() <= 0.85) &
                (((pl.col("ask") - pl.col("bid")) / ((pl.col("bid") + pl.col("ask")) / 2)) <= 0.04)
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
    if "delta_volume" in df_res.columns:
        # Measure pure volume magnitude surge.
        # Price direction is already verified by s_momentum and s_vwap.
        # Multiplying by price direction was causing sign(0)=0 bugs when LTP stayed flat during block orders.
        df_res = df_res.with_columns(
            (pl.col("delta_volume").abs() / (pl.col("delta_volume").abs().rolling_mean(5).over(pk) + 1.0))
            .fill_null(0).fill_nan(0).clip(0, 20).alias("volume_burst")
        )
        # Apply a rolling max so the volume impulse "stays alive" for 5 ticks.
        # Otherwise, a subsequent bid/ask quote update with 0 volume will become the .last() row and hide the burst.
        df_res = df_res.with_columns(
            pl.col("volume_burst").rolling_max(5).over(pk).alias("volume_burst")
        )
    if "delta_oi" in df_res.columns:
        df_res = df_res.with_columns((pl.col("delta_oi") - pl.col("delta_oi").shift(1).over(pk)).fill_null(0).alias("oi_accel"))
        if "bid" in df_res.columns and "ask" in df_res.columns:
            df_res = df_res.with_columns(((pl.col("ask") - pl.col("bid")).abs() / (((pl.col("ask") + pl.col("bid")) / 2) + 1e-8)).alias("_spread_pct"))
            df_res = df_res.with_columns(
                (pl.col("oi_accel") * pl.when(pl.col("_spread_pct") > 0.01).then(0.1).otherwise(1.0 - (pl.col("_spread_pct") * 50).clip(0, 0.9)))
                .alias("oi_accel")
            )
            df_res = df_res.drop(["_spread_pct"])
    
    # ── TAKE SNAPSHOT (must sort by real_timestamp so keep='last' gets the freshest tick) ──
    sort_col = "real_timestamp" if "real_timestamp" in df_res.columns else "timestamp"
    df_res = df_res.sort(sort_col)
    df_latest = df_res.unique(subset=pk, keep="last")
    
    # CRITICAL FIX: Filter out stale ticks. If an option hasn't traded in 30 seconds, 
    # the data feed dropped it. Do not trade on stale prices.
    if "real_timestamp" in df_latest.columns:
        if date_str is None and not dry_run:
            # LIVE TRADING: Use actual wall-clock time to detect global feed lag
            current_time_ms = time.time() * 1000
        else:
            # BACKTESTING: Use the max timestamp in the chunk
            current_time_ms = df_res["real_timestamp"].max() 
            
        if current_time_ms is not None:
            df_latest = df_latest.filter((current_time_ms - pl.col("real_timestamp")) < 30_000)
        
    if df_latest.is_empty():
        return pl.DataFrame()
        
    scores = []
    
    # ── COMPUTE ABSOLUTE STRUCTURAL SCORES (Z-SCORE REPLACEMENT) ──
    # Replaces cross-sectional Z-scores with absolute momentum alignment
    # ── HARD EXHAUSTION BLOCK (Mean Expansion) ──
    # If the spot price has stretched far from the VWAP (> 0.35%), the move is "already done".
    # We do NOT buy parabolic rips, regardless of how strong Institutional OI is. A pullback is mathematically inevitable.
    if "vwap_deviation" in df_latest.columns:
        max_dev = df_latest["vwap_deviation"].abs().max()
        if max_dev > 0.0035:
            log.info(f"MOMENTUM ENGINE: Blocked — price is parabolically over-extended (vwap_dev={max_dev:.4f} > 0.0035). Awaiting pullback.")
            return pl.DataFrame()
            
    # ── COMPUTE MOMENTUM FEATURES ──
    # 1. Structural Trend: Price vs VWAP (Scale -50 to +50)
    # vwap_deviation is typically -0.01 to +0.01 (-1% to +1%). Multiply by 5000 -> score of -50 to +50.
    # FIX: If price is massively extended (> 0.20%), cap the VWAP score at +20 so it doesn't blindly rubber-stamp 
    # massive parabolic moves, but don't kill it entirely so we don't miss 1% trend days.
    # By clipping the final score to (-50, +20), we mathematically cap the reward for BOTH CE and PE,
    # while preserving the massive -50 penalty for being on the wrong side of the trend.
    if "vwap_deviation" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (
                (pl.col("vwap_deviation") * 5000.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1)
            ).clip(lower_bound=-50.0, upper_bound=20.0).fill_null(0).fill_nan(0).alias("s_vwap")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_vwap"))

    if "dpcr_dt" in df_latest.columns:
        # dpcr_dt > 0 means put writing (bullish).
        # Observed range: -0.004 to +0.018. Multiply by 500 to get scores in -2 to +9 range.
        df_latest = df_latest.with_columns(
            ((pl.col("dpcr_dt") * 500.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1))
            .clip(-30, 30).fill_null(0).fill_nan(0).alias("s_oi_flow")
        )
    elif "nse_pcr_oi" in df_latest.columns:
        # Fallback to absolute PCR
        df_latest = df_latest.with_columns(
            (((pl.col("nse_pcr_oi") - 1.0) * 15.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1))
            .clip(-30, 30).fill_null(0).fill_nan(0).alias("s_oi_flow")
        )
    elif "oi_accel" in df_latest.columns:
        # Fallback to local OI acceleration
        # If OI is accelerating and price is moving in our favor, that's institutional flow.
        df_latest = df_latest.with_columns(
            (pl.col("oi_accel") / 100.0)
            .clip(-30, 30).fill_null(0).fill_nan(0).alias("s_oi_flow")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_oi_flow"))
        
    # 3. Short-Term Momentum: Price Velocity or EMA Cross (Scale -30 to +30)
    # FIX: Divergence Filter. If price spikes parabolically BUT Institutional OI Flow is weak (< 15), 
    # it's a retail fakeout. Penalize it to wait for the pullback.
    # If OI Flow is MASSIVE (> 15), it's a true Short Squeeze / Momentum Blast. Let it ride!
    if "ema_cross_pct" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (
                # EXHAUSTION FILTER: Do not catch the aftermath of a massive spike
                # Observed range: -0.000007 to +0.000015. Adjusted thresholds accordingly.
                pl.when(pl.col("ema_cross_pct").abs() > 0.0005)
                .then(pl.lit(-50.0))
                .when((pl.col("ema_cross_pct").abs() > 0.0003) & (pl.col("s_oi_flow").abs() < 15.0))
                .then(pl.lit(-30.0)) # Fakeout penalty
                .otherwise(
                    (pl.col("ema_cross_pct") * 500000.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1)
                )
            ).clip(-50, 30).fill_null(0).fill_nan(0).alias("s_momentum")
        )
    elif "price_velocity" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (
                # EXHAUSTION FILTER: Do not catch the aftermath of a massive spike
                pl.when(pl.col("price_velocity").abs() > 0.0500)
                .then(pl.lit(-50.0))
                .when((pl.col("price_velocity").abs() > 0.0300) & (pl.col("s_oi_flow").abs() < 15.0))
                .then(pl.lit(-30.0)) # Fakeout penalty
                .otherwise(
                    (pl.col("price_velocity") * 10000.0)
                )
            ).clip(-50, 30).fill_null(0).fill_nan(0).alias("s_momentum")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_momentum"))

    # ── EURO OPEN TEMPORAL TRAP (1:50 PM - 1:55 PM) ──
    # If structural trend (VWAP) perfectly aligns with institutional flow, aggressively force the breakout!
    now_hour = datetime.now().hour
    now_minute = datetime.now().minute
    if now_hour == 13 and 50 <= now_minute <= 55:
        if "vwap_deviation" in df_latest.columns and "s_oi_flow" in df_latest.columns:
            df_latest = df_latest.with_columns(
                pl.when(
                    (pl.col("vwap_deviation") > 0.001) & 
                    (pl.col("s_oi_flow") > 10.0) & 
                    (pl.col("option_type") == "CE")
                )
                .then(pl.col("s_momentum") + 40.0)
                .when(
                    (pl.col("vwap_deviation") < -0.001) & 
                    (pl.col("s_oi_flow") < -10.0) & 
                    (pl.col("option_type") == "PE")
                )
                .then(pl.col("s_momentum") + 40.0)
                .otherwise(pl.col("s_momentum"))
                .clip(-50, 50)
                .alias("s_momentum")
            )
    # Time-of-Day modifier
    now_hour = datetime.now().hour
    now_minute = datetime.now().minute
    
    # Penalize early morning chop
    if now_hour < 10 or (now_hour == 10 and now_minute < 15):
        tod_multiplier = 0.5
    # EURO OPEN TREND: 12:45 PM to 1:30 PM (Actively capture the European institutional move)
    elif (now_hour == 12 and now_minute >= 45) or (now_hour == 13 and now_minute <= 30):
        tod_multiplier = 1.15
    # LATE-DAY PENALTY: After 2:30 PM the bulk of the intraday move is done.
    # Entering new momentum trades this late catches tail-end exhaustion, not breakouts.
    # Power Hour / CAS engines handle late-day separately.
    elif now_hour >= 15 or (now_hour == 14 and now_minute >= 30):
        tod_multiplier = 0.6
    else:
        tod_multiplier = 1.0
    
    # ── ADAPTIVE ENTRY THRESHOLDS (Stop Catching Exhaustion Tops) ──
    # If institutional OI is extremely strong, we want to enter EARLY.
    # Waiting for massive volume and momentum causes us to buy the exhaustion top.
    if abs(macro_oi_net) >= 8.0:
        REQUIRED_VOLUME = 1.0      # Normal volume is fine, get in early
        FEATURE_THRESHOLD = 0.5    # Accept early momentum signals
        REQUIRED_FEATURES = 1      # Only need 1 confirming signal
    elif abs(macro_oi_net) >= 4.0:
        REQUIRED_VOLUME = 1.2      # Moderate volume burst is enough
        FEATURE_THRESHOLD = 1.0    # 1 Std Dev is enough to confirm
        REQUIRED_FEATURES = 1      # Only need 1 confirming signal due to decent trend
    else:
        REQUIRED_VOLUME = 1.5      # Need a massive volume burst to confirm
        FEATURE_THRESHOLD = 1.25   # Need strong momentum (1.25 SD)
        REQUIRED_FEATURES = 2      # Need 2 confirming factors since trend is weak
        
    # ── MANDATORY VOLUME VERIFICATION GATE ──
    if "volume_burst" in df_latest.columns:
        max_burst = df_latest["volume_burst"].max()
        if max_burst is None:
            max_burst = 0.0
            
        log.info(f"DEBUG [{df_latest['underlying'][0] if not df_latest.is_empty() else 'None'}]: Max volume_burst seen = {max_burst}")
        
        df_latest = df_latest.filter(pl.col("volume_burst") >= REQUIRED_VOLUME)
        if df_latest.is_empty():
            log.info(f"MOMENTUM ENGINE: Blocked — volume burst ({max_burst:.2f}) < required ({REQUIRED_VOLUME})")
            return pl.DataFrame()
            
    # ── MULTI-FACTOR CONFLUENCE GATE ──
    df_latest = df_latest.with_columns([
        (pl.col("s_vwap") >= FEATURE_THRESHOLD).cast(pl.Int32).alias("_f_vwap"),
        (pl.col("s_oi_flow") >= FEATURE_THRESHOLD).cast(pl.Int32).alias("_f_oi"),
        (pl.col("s_momentum") >= FEATURE_THRESHOLD).cast(pl.Int32).alias("_f_mom"),
    ])
    df_latest = df_latest.with_columns(
        (pl.col("_f_vwap") + pl.col("_f_oi") + pl.col("_f_mom")).alias("_feature_count")
    )
    
    # Log feature values for debugging
    if df_latest.height > 0:
        sample = df_latest.row(0, named=True)
        log.info("MOMENTUM FEATURES: s_vwap=%.2f s_oi_flow=%.2f s_momentum=%.2f | active_features=%d/3",
                 sample.get("s_vwap", 0), sample.get("s_oi_flow", 0), sample.get("s_momentum", 0),
                 sample.get("_feature_count", 0))
    
    # GATE: Require non-zero features for confluence
    df_latest = df_latest.filter(pl.col("_feature_count") >= REQUIRED_FEATURES)
    if df_latest.is_empty():
        log.info(f"MOMENTUM ENGINE: Blocked — insufficient feature confluence (< {REQUIRED_FEATURES} active features)")
        return pl.DataFrame()
    
    # Drop temp columns
    df_latest = df_latest.drop(["_f_vwap", "_f_oi", "_f_mom", "_feature_count"])
    
    # Base score sum
    # ── PULLBACK RE-ENTRY HUNTING ──
    # If price has pulled back to a healthy VWAP zone (0.0008 <= vwap_dev <= 0.0030) while Institutional OI is high (>= 10.0),
    # give it a calibrated +5.0 score boost (gentle nudge, not overwhelming).
    is_pullback_reentry = False
    if "vwap_deviation" in df_latest.columns:
        max_dev = df_latest["vwap_deviation"].abs().max()
        if 0.0008 <= max_dev <= 0.0030 and abs(macro_oi_net) >= 10.0:
            is_pullback_reentry = True
            log.info("MOMENTUM ENGINE: Pullback Re-Entry setup detected (vwap_dev=%.4f, oi=%.1f) — applying +5 score boost", max_dev, macro_oi_net)

    pullback_boost = 5.0 if is_pullback_reentry else 0.0

    df_latest = df_latest.with_columns(
        (((pl.col("s_vwap") + pl.col("s_oi_flow") + pl.col("s_momentum")) * tod_multiplier) + pullback_boost).alias("raw_score")
    )
    
    # Scale raw score directly to composite_alpha_score (-100 to 100)
    df_latest = df_latest.with_columns(
        pl.col("raw_score").clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    
    # GATE: Dynamic Minimum Absolute Score
    # If institutional flow is massive (>= 10.0), lower the threshold to 5.0 to front-run the breakout.
    # Otherwise, require a strict 10.0 magnitude to filter out noise.
    if abs(macro_oi_net) >= 10.0:
        MIN_COMPOSITE_SCORE = 5.0
    else:
        MIN_COMPOSITE_SCORE = 10.0
        
    df_latest = df_latest.filter(pl.col("composite_alpha_score") >= MIN_COMPOSITE_SCORE)
    if df_latest.is_empty():
        log.info("MOMENTUM ENGINE: Blocked — composite_alpha_score below minimum threshold (< %.0f)", MIN_COMPOSITE_SCORE)
        return pl.DataFrame()
    
    if "strike" in df_latest.columns:
        df_latest = df_latest.filter(pl.col("strike") > 0)
        
    # ── MACRO TREND ALIGNMENT ──
    # If the overall market structure is strongly skewed, block counter-trend momentum fakeouts.
    # Use OI Net >= 5.0 for both indices. This is achievable on real trend days (today Nifty hit 5.4+ early,
    # BankNifty was always 10+) while still filtering out directionless chop (OI < 5).
    oi_trend_thresh = 5.0
    if macro_oi_net <= -oi_trend_thresh:
        # Bearish macro: Block CE
        df_latest = df_latest.filter(pl.col("option_type") != "CE")
    elif macro_oi_net >= oi_trend_thresh:
        # Bullish macro: Block PE
        df_latest = df_latest.filter(pl.col("option_type") != "PE")
        
    if df_latest.is_empty():
        log.info("MOMENTUM ENGINE: Blocked — counter to macro trend (oi_net=%.2f, threshold=%.1f)", macro_oi_net, oi_trend_thresh)
        return pl.DataFrame()
        
    df_latest = df_latest.with_columns(pl.lit(True).alias("is_trending"))
    df_univ = build_momentum_universe(df_latest)
    if df_univ.is_empty():
        return pl.DataFrame()
        
    df_scored = score_momentum_opportunities(df_univ)
    df_ranked = rank_opportunities(df_scored)
    df_conf = calculate_strategy_confidence(df_ranked, "Momentum Breakout")
    df_conf = df_conf.with_columns([
        pl.lit("BUY").alias("action"),
        pl.lit("Momentum Breakout").alias("_engine")
    ])
    return df_conf

def run_mean_reversion_engine(df_res, t0, latest_spot_direction="NEUTRAL", macro_oi_net=0.0):
    """
    Strategy B: Intraday Mean Reversion (Choppy Markets)
    Hunts for micro-reversions in range-bound markets. When price deviates from VWAP
    or touches Bollinger Band extremes, this engine buys the counter-direction option
    to ride the snap-back to the mean.
    """
    # pyrefly: ignore [missing-import]
    import polars as pl
    
    if df_res.is_empty():
        return pl.DataFrame()
        
    unique_strikes = df_res["strike"].n_unique()
    if unique_strikes < 5:
        log.debug("MR_ENGINE: Skipped — only %d unique strikes (need 5+)", unique_strikes)
        return pl.DataFrame()
        
    # Trim to Deep ITM / Near-ITM (aligned with scorer target delta 0.78)
    pre_filter_count = df_res.height
    if "delta" in df_res.columns:
        df_filtered = df_res.filter(
            (pl.col("volume") > 5000) & 
            (pl.col("delta").abs() >= 0.55) & 
            (pl.col("delta").abs() <= 0.90)
        )
        if df_filtered.height < 10:
            df_filtered = df_res.filter(
                (pl.col("volume") > 1000) &
                (pl.col("delta").abs() >= 0.45) & 
                (pl.col("delta").abs() <= 0.92)
            )
        df_res = df_filtered
    
    log.debug("MR_ENGINE: Delta+Volume filter: %d → %d rows", pre_filter_count, df_res.height)
    if df_res.is_empty():
        log.info("MR_ENGINE: No options pass delta/volume filter")
        return pl.DataFrame()
    
    # ── DIRECTIONAL BIAS FILTER ──
    # Even in a genuine choppy range, institutional flow still has a mild directional bias.
    # If OI skew > 2%, only trade options that align with the flow direction.
    # Bearish OI (< -2%) → Only buy PEs (fade bounces back down toward VWAP)
    # Bullish OI (> +2%) → Only buy CEs (fade dips back up toward VWAP)
    # This prevents the MR engine from ever buying CEs in a bearish market or PEs in a bullish market.
    OI_BIAS_THRESHOLD = 2.0
    if macro_oi_net <= -OI_BIAS_THRESHOLD:
        pre_bias = df_res.height
        df_res = df_res.filter(pl.col("option_type") == "PE")
        if df_res.is_empty():
            log.info("MR_ENGINE: Directional bias filter removed all CEs (oi_net=%.2f, only PEs allowed)", macro_oi_net)
            return pl.DataFrame()
        log.info("MR_ENGINE BIAS: Bearish OI (%.2f%%) → filtered to PEs only (%d → %d)", macro_oi_net, pre_bias, df_res.height)
    elif macro_oi_net >= OI_BIAS_THRESHOLD:
        pre_bias = df_res.height
        df_res = df_res.filter(pl.col("option_type") == "CE")
        if df_res.is_empty():
            log.info("MR_ENGINE: Directional bias filter removed all PEs (oi_net=%.2f, only CEs allowed)", macro_oi_net)
            return pl.DataFrame()
        log.info("MR_ENGINE BIAS: Bullish OI (%.2f%%) → filtered to CEs only (%d → %d)", macro_oi_net, pre_bias, df_res.height)
        
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    if "ltp" in df_res.columns:
        df_res = df_res.with_columns(
            ((pl.col("ltp") - pl.col("ltp").rolling_mean(3).over(pk)) / (pl.col("ltp").rolling_mean(3).over(pk) + 1e-8))
            .fill_null(0).fill_nan(0).alias("price_velocity")
        )
        
    sort_col = "real_timestamp" if "real_timestamp" in df_res.columns else "timestamp"
    df_res = df_res.sort(sort_col)
    df_latest = df_res.unique(subset=pk, keep="last")
    
    pre_stale_count = df_latest.height
    if "real_timestamp" in df_latest.columns:
        current_time_ms = time.time() * 1000
        # Allow 60s staleness for choppy markets (data arrives less frequently on low-vol options)
        df_latest = df_latest.filter((current_time_ms - pl.col("real_timestamp")) < 60_000)
    
    log.debug("MR_ENGINE: Staleness filter: %d → %d rows", pre_stale_count, df_latest.height)
    if df_latest.is_empty():
        log.info("MR_ENGINE: All data stale (>60s old)")
        return pl.DataFrame()
        
    # ── COMPUTE REVERSAL SCORES ──
    
    # 1. VWAP Fade Score (Reward over-extension from VWAP)
    # In choppy markets, VWAP deviations are SMALL (0.01-0.04% = 2-10 pts on NIFTY).
    # Use 25000x multiplier so a 0.02% deviation (5pts NIFTY) gives score ~5.0.
    # Direction flip: CE gets -1 (spot above VWAP = bearish for CEs), PE gets +1.
    if "vwap_deviation" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (
                (pl.col("vwap_deviation") * 25000.0) * pl.when(pl.col("option_type") == "CE").then(-1).otherwise(1)
            ).clip(-50, 50).fill_null(0).fill_nan(0).alias("s_vwap_fade")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_vwap_fade"))
    
    # 2. Bollinger Band Reversal Score (Alternative to VWAP deviation)
    # %B > 0.85 = near upper band (overbought → buy PEs), %B < 0.15 = near lower band (oversold → buy CEs)
    if "bb_pct_b" in df_latest.columns:
        df_latest = df_latest.with_columns(
            pl.when((pl.col("bb_pct_b") > 0.80) & (pl.col("option_type") == "PE"))
            .then((pl.col("bb_pct_b") - 0.50) * 20.0)  # 0.85 → 7.0, 0.95 → 9.0
            .when((pl.col("bb_pct_b") < 0.20) & (pl.col("option_type") == "CE"))
            .then((0.50 - pl.col("bb_pct_b")) * 20.0)  # 0.15 → 7.0, 0.05 → 9.0
            .otherwise(0.0)
            .clip(0, 30).fill_null(0).fill_nan(0).alias("s_bb_reversal")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_bb_reversal"))
        
    # 3. Exhaustion Score (Option Price Velocity in trade direction)
    if "price_velocity" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (pl.col("price_velocity") * 1000.0)
            .clip(-30, 30).fill_null(0).fill_nan(0).alias("s_exhaustion")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_exhaustion"))
        
    # 4. Fakeout Check (OI Flow must be weak — no institutional breakouts)
    if "dpcr_dt" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("dpcr_dt") * 500.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1))
            .clip(-30, 30).fill_null(0).fill_nan(0).alias("s_oi_flow_raw")
        )
    elif "nse_pcr_oi" in df_latest.columns:
        df_latest = df_latest.with_columns(
            (((pl.col("nse_pcr_oi") - 1.0) * 15.0) * pl.when(pl.col("option_type") == "CE").then(1).otherwise(-1))
            .clip(-30, 30).fill_null(0).fill_nan(0).alias("s_oi_flow_raw")
        )
    else:
        df_latest = df_latest.with_columns(pl.lit(0.0).alias("s_oi_flow_raw"))
    
    # ── DIAGNOSTIC: Log score distribution before gating ──
    if not df_latest.is_empty():
        vwap_max = float(df_latest["s_vwap_fade"].max())
        bb_max = float(df_latest["s_bb_reversal"].max())
        exh_max = float(df_latest["s_exhaustion"].max())
        oi_min = float(df_latest["s_oi_flow_raw"].abs().min())
        log.info("MR_ENGINE SCORES: %d options | vwap_fade_max=%.2f | bb_reversal_max=%.2f | exhaustion_max=%.2f | oi_flow_min=%.2f",
                 df_latest.height, vwap_max, bb_max, exh_max, oi_min)
    
    # ── SIGNAL GATE (OR-based: VWAP fade OR Bollinger reversal) ──
    # Primary signal: VWAP over-extension (score > 1.0)
    # Alternative signal: Bollinger Band extreme (%B score > 3.0)
    # Exhaustion is supplementary (adds score but not mandatory)
    # OI flow must be weak (no institutional breakout confirmation)
    pre_gate_count = df_latest.height
    df_latest = df_latest.filter(
        (
            (pl.col("s_vwap_fade") > 1.0) |          # VWAP over-extension
            (pl.col("s_bb_reversal") > 3.0)           # Bollinger Band extreme
        ) & 
        (pl.col("s_oi_flow_raw").abs() < 10.0)        # No institutional breakout
    )
    
    log.info("MR_ENGINE GATE: %d → %d passed signal gate (vwap_fade>1.0 OR bb_reversal>3.0) & (oi_flow<10)", 
             pre_gate_count, df_latest.height)
    
    if df_latest.is_empty():
        return pl.DataFrame()
        
    # Base score: best of VWAP fade or BB reversal, plus exhaustion bonus
    # LATE-DAY PENALTY: After 2:30 PM, penalize MR scores so Strategy C/D (Power Hour/CAS) take priority.
    # Mean Reversion fades become increasingly dangerous as end-of-day positioning takes over.
    mr_now_hour = datetime.now().hour
    mr_now_minute = datetime.now().minute
    mr_tod_mult = 0.6 if (mr_now_hour >= 15 or (mr_now_hour == 14 and mr_now_minute >= 30)) else 1.0
    
    df_latest = df_latest.with_columns(
        (
            (
                pl.when(pl.col("s_vwap_fade") > pl.col("s_bb_reversal"))
                .then(pl.col("s_vwap_fade"))
                .otherwise(pl.col("s_bb_reversal"))
                + pl.col("s_exhaustion").clip(lower_bound=0)  # Only add positive exhaustion
            ) * mr_tod_mult
        ).alias("raw_score")
    )
    
    # Scale raw score directly to composite_alpha_score (-100 to 100)
    df_latest = df_latest.with_columns(
        (pl.col("raw_score") * 2.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    
    # Composite threshold (lowered from 25 to 10 — confidence system gates at 0.70 anyway)
    MIN_COMPOSITE_SCORE = 10.0 
    pre_comp_count = df_latest.height
    df_latest = df_latest.filter(pl.col("composite_alpha_score") >= MIN_COMPOSITE_SCORE)
    log.info("MR_ENGINE COMPOSITE: %d → %d passed composite >= %.1f", pre_comp_count, df_latest.height, MIN_COMPOSITE_SCORE)
    
    if df_latest.is_empty():
        return pl.DataFrame()
        
    if "strike" in df_latest.columns:
        df_latest = df_latest.filter(pl.col("strike") > 0)
        
    df_latest = df_latest.with_columns(pl.lit(False).alias("is_trending"))
    df_univ = build_mean_reversion_universe(df_latest)
    if df_univ.is_empty():
        log.info("MR_ENGINE: Universe builder returned empty")
        return pl.DataFrame()
        
    df_scored = score_mean_reversion_opportunities(df_univ)
    df_ranked = rank_opportunities(df_scored)
    df_conf = calculate_strategy_confidence(df_ranked, "Mean Reversion")
    
    if not df_conf.is_empty():
        log.info("MR_ENGINE: ✅ %d candidates with confidence range [%.3f, %.3f]",
                 df_conf.height, float(df_conf["confidence"].min()), float(df_conf["confidence"].max()))
    
    df_conf = df_conf.with_columns([
        pl.lit("BUY").alias("action"),
        pl.lit("Mean Reversion").alias("_engine")
    ])
    return df_conf


def run_power_hour_engine(df_res, t0, spot, vwap_val, oi_net, underlying):
    """
    Strategy C: Power Hour Expiry Unwind (2:45 PM - 3:35 PM on Expiry Days Only)
    
    Exploits the institutional closing auction effect where:
    - Spot > VWAP + OI bearish → Institutions dumping longs → Buy PUTs
    - Spot < VWAP + OI bullish → Short covering rally → Buy CALLs
    
    Only fires when VWAP displacement AND OI direction form a confluence signal.
    Selects ATM/near-ATM options for maximum gamma exposure.
    """
    # pyrefly: ignore [missing-import]
    import polars as pl
    
    if df_res.is_empty():
        return pl.DataFrame()
    
    # ── TRUE GAMMA BLAST DETECTOR (Short Covering Panic) ──
    # A true Gamma Squeeze isn't about macro trend accumulation. It's about Option Sellers
    # getting trapped and being forced to market-buy to cover their shorts.
    # Mathematical Signature: Price accelerates + Volume spikes + Open Interest PLUMMETS (delta_oi < 0)
    
    vwap_dev_pct = (spot - vwap_val) / vwap_val if vwap_val > 0 else 0
    
    # We only look at options within 0.5% of spot (ATM) because that's where Gamma is highest
    if "strike" in df_res.columns and "spot" in df_res.columns:
        df_atm = df_res.filter(
            ((pl.col("strike") - pl.col("spot")).abs() / pl.col("spot")) < 0.005
        )
    else:
        return pl.DataFrame()
        
    if df_atm.is_empty():
        return pl.DataFrame()
        
    # THE TRIPLE-THREAT GAMMA BLAST SIGNATURE
    # 1. Short Covering Panic: delta_oi < -1000 (Sellers abandoning ship)
    # 2. High Urgency Volume: delta_volume > 5000 (Panic surge in the last minute)
    # 3. Order Book Lifting (IV Spike Proxy): ltp is violently pressing against the ask price
    if all(col in df_atm.columns for col in ["delta_oi", "delta_volume", "ltp", "bid", "ask"]):
        df_atm = df_atm.with_columns(
            ((pl.col("ltp") - pl.col("bid")) / (pl.col("ask") - pl.col("ltp") + 1e-5)).alias("ba_pressure")
        )
        df_panic = df_atm.filter(
            (pl.col("delta_oi") < -500) & 
            (pl.col("delta_volume") > 1500) &
            (pl.col("ba_pressure") > 1.2) # Buyers are sweeping the ask
        )
    else:
        log.info("[%s] POWER HOUR: Missing required columns for Gamma Blast detection.", underlying)
        return pl.DataFrame()
        
    if df_panic.is_empty():
        log.info("[%s] POWER HOUR: No Triple-Threat panic signatures detected at ATM strikes.", underlying)
        return pl.DataFrame()
        
    # 4. Convexity Breakout (Spot Price Velocity Confirmation)
    # Spot must be breaking out violently (>= 0.15% deviation from VWAP)
    df_bull_squeeze = df_panic.filter(
        (pl.col("option_type") == "CE") & (pl.lit(vwap_dev_pct) > 0.0015)
    )
    
    df_bear_squeeze = df_panic.filter(
        (pl.col("option_type") == "PE") & (pl.lit(vwap_dev_pct) < -0.0015)
    )
    
    df_filtered = pl.DataFrame()
    setup_name = ""
    confluence_strength = 0.0
    
    if not df_bull_squeeze.is_empty():
        df_filtered = df_bull_squeeze
        setup_name = "TRUE_GAMMA_BLAST_BULL"
        confluence_strength = 1.0  # Max confidence for true panic
        log.info("[%s] 🧨 TRUE GAMMA BLAST DETECTED (BULLISH): Call Sellers are trapped and covering!", underlying)
    elif not df_bear_squeeze.is_empty():
        df_filtered = df_bear_squeeze
        setup_name = "TRUE_GAMMA_BLAST_BEAR"
        confluence_strength = 1.0  # Max confidence for true panic
        log.info("[%s] 🧨 TRUE GAMMA BLAST DETECTED (BEARISH): Put Sellers are trapped and covering!", underlying)
    else:
        log.info("[%s] POWER HOUR: Panic signature present, but price velocity does not confirm breakout direction.", underlying)
        return pl.DataFrame()
    
    # ── SNAPSHOT AND SCORE ──
    # Get the latest snapshot of the panic options
    sort_col = "real_timestamp" if "real_timestamp" in df_filtered.columns else "timestamp"
    df_filtered = df_filtered.sort(sort_col)
    df_latest = df_filtered.unique(subset=["underlying", "expiry", "strike", "option_type"], keep="last")
    
    if df_latest.is_empty():
        return pl.DataFrame()
    
    # Select ATM options: strikes within 0.5% of spot price (tight ATM band for gamma)
    if "strike" in df_latest.columns and "spot" in df_latest.columns:
        df_latest = df_latest.filter(
            ((pl.col("strike") - pl.col("spot")).abs() / pl.col("spot")) < 0.005
        )
    
    if df_latest.is_empty():
        log.info("[%s] POWER HOUR: No ATM strikes within 0.5%% of spot", underlying)
        return pl.DataFrame()
    
    # Liquidity filters: Must have decent volume and tight spread
    if "volume" in df_latest.columns:
        df_latest = df_latest.filter(pl.col("volume") > 1000)
    
    if "bid" in df_latest.columns and "ask" in df_latest.columns:
        df_latest = df_latest.with_columns(
            ((pl.col("ask") - pl.col("bid")) / ((pl.col("bid") + pl.col("ask")) / 2 + 1e-5)).alias("_ph_spread")
        )
        df_latest = df_latest.filter(pl.col("_ph_spread") <= 0.015)  # Max 1.5% spread
        df_latest = df_latest.drop("_ph_spread")
    
    if df_latest.is_empty():
        log.info("[%s] POWER HOUR: All ATM strikes failed liquidity filters", underlying)
        return pl.DataFrame()
    
    # Build universe and score with Strategy D Expiry Gamma Scorer
    df_univ = build_closing_auction_universe(df_latest)
    if df_univ.is_empty():
        return pl.DataFrame()
    
    df_scored = score_expiry_gamma_opportunities(df_univ)
    df_ranked = rank_opportunities(df_scored)
    df_conf = calculate_strategy_confidence(df_ranked, "Expiry Gamma")
    df_conf = df_conf.with_columns([
        pl.lit("BUY").alias("action"),
        pl.lit(f"EXPIRY_POWER_HOUR_{setup_name}").alias("_engine")
    ])
    log.info("[%s] STRATEGY D EXPIRY GAMMA: %d candidates generated.", 
             underlying, df_conf.height if not df_conf.is_empty() else 0)
    return df_conf


def run_closing_auction_engine(df_res, t0, spot, vwap_val, oi_net, underlying):
    """
    Strategy C: Daily Closing Auction Session Engine (3:15 PM - 3:35 PM IST Daily).
    Exploits EOD Closing Auction Imbalances on Non-Expiry Days.
    """
    # pyrefly: ignore [missing-import]
    import polars as pl
    if df_res.is_empty():
        return pl.DataFrame()

    pk = ["underlying", "expiry", "strike", "option_type"]
    sort_col = "real_timestamp" if "real_timestamp" in df_res.columns else "timestamp"
    df_res = df_res.sort(sort_col)
    df_latest = df_res.unique(subset=pk, keep="last")

    if df_latest.is_empty():
        return pl.DataFrame()

    # Directional Alignment for Closing Imbalance
    # CAS Adaptation (Aug 3): Cash market spot freezes at 3:15 PM, so spot vs vwap_val becomes stale/distorted.
    # We now rely entirely on derivatives macro_oi_net which remains live until 3:40 PM.
    if oi_net >= 1.0:
        df_latest = df_latest.filter(pl.col("option_type") == "CE")
    elif oi_net <= -1.0:
        df_latest = df_latest.filter(pl.col("option_type") == "PE")
    else:
        log.info("[%s] STRATEGY C CLOSING AUCTION: Contradictory flow (OI Net %.2f is too neutral without live spot). Skipping.", underlying, oi_net)
        return pl.DataFrame()

    if df_latest.is_empty():
        log.info("[%s] STRATEGY C CLOSING AUCTION: No candidates aligned with closing direction.", underlying)
        return pl.DataFrame()

    # Filter near-ATM options (within 1.0% of spot) with premium <= 180 for closing auction liquidity
    if "strike" in df_latest.columns and "spot" in df_latest.columns:
        df_latest = df_latest.filter(
            ((pl.col("strike") - pl.col("spot")).abs() / pl.col("spot")) < 0.010
        )

    if df_latest.is_empty():
        return pl.DataFrame()

    df_univ = build_closing_auction_universe(df_latest)
    if df_univ.is_empty():
        return pl.DataFrame()

    df_scored = score_closing_auction_opportunities(df_univ)
    df_ranked = rank_opportunities(df_scored)
    df_conf = calculate_strategy_confidence(df_ranked, "Closing Auction", macro_cached_data)
    df_conf = df_conf.with_columns([
        pl.lit("BUY").alias("action"),
        pl.lit("CLOSING_AUCTION_IMBALANCE").alias("_engine")
    ])
    log.info("[%s] STRATEGY C CLOSING AUCTION: %d candidates generated.",
             underlying, df_conf.height if not df_conf.is_empty() else 0)
    return df_conf

@njit
def _vectorized_greeks(spots, strikes, ts, ivs, rs, is_calls):
    n = len(spots)
    deltas = np.empty(n, dtype=np.float64)
    gammas = np.empty(n, dtype=np.float64)
    thetas = np.empty(n, dtype=np.float64)
    
    for i in range(n):
        spot = spots[i]
        strike = strikes[i]
        t = max(ts[i], 0.0001)
        iv = max(ivs[i], 0.01)
        r = rs[i]
        is_call = is_calls[i]
        
        if spot <= 0 or strike <= 0:
            deltas[i] = 0.5
            gammas[i] = 0.0
            thetas[i] = 0.0
            continue
            
        d1 = (math.log(spot / strike) + (r + (iv ** 2) / 2) * t) / (iv * math.sqrt(t))
        d2 = d1 - iv * math.sqrt(t)
        
        call_delta = (1.0 + math.erf(d1 / math.sqrt(2.0))) / 2.0
        deltas[i] = call_delta if is_call else (call_delta - 1.0)
        
        pdf_d1 = math.exp(- (d1 ** 2) / 2.0) / math.sqrt(2.0 * math.pi)
        gammas[i] = pdf_d1 / (spot * iv * math.sqrt(t))
        
        term1 = -(spot * iv * pdf_d1) / (2 * math.sqrt(t))
        if is_call:
            nd2 = (1.0 + math.erf(d2 / math.sqrt(2.0))) / 2.0
            thetas[i] = (term1 - r * strike * math.exp(-r * t) * nd2) / 365.0
        else:
            n_neg_d2 = (1.0 + math.erf(-d2 / math.sqrt(2.0))) / 2.0
            thetas[i] = (term1 + r * strike * math.exp(-r * t) * n_neg_d2) / 365.0
            
    return deltas, gammas, thetas

@njit(fastmath=True, cache=True)
def norm_cdf(x):
    """Fast approximation of Cumulative Distribution Function."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

@njit(fastmath=True, cache=True)
def norm_pdf(x):
    """Probability Density Function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

@njit(fastmath=True, cache=True)
def bs_price_and_vega(S, K, T, r, sigma, is_call):
    """
    Computes both Price and Vega simultaneously for efficiency in the NR loop.
    """
    # Handle edge case where option is dead (T=0)
    if T <= 0.0:
        return (max(0.0, S - K) if is_call else max(0.0, K - S)), 0.0
        
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    vega = S * norm_pdf(d1) * math.sqrt(T)
    
    if is_call:
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        
    return price, vega

@njit(fastmath=True, cache=True)
def calculate_live_iv(S, K, T, r, market_price, is_call, max_iter=50, tol=1e-4):
    """
    Newton-Raphson solver to find Implied Volatility from Live LTP.
    Returns IV as a decimal (e.g., 0.15 for 15%).
    """
    # Check intrinsic value limits to prevent infinite loops on deep ITM/arbitrage options
    intrinsic = max(0.0, S - K) if is_call else max(0.0, K - S)
    if market_price <= intrinsic:
        return 0.001 # Minimum IV bound

    # Initial guess: 30% IV (typical for Nifty/BankNifty)
    sigma = 0.30 
    
    for i in range(max_iter):
        price, vega = bs_price_and_vega(S, K, T, r, sigma, is_call)
        
        diff = price - market_price
        
        # If difference is within tolerance, we found the IV
        if abs(diff) < tol:
            return sigma
            
        # If Vega is too small, NR will overshoot wildly (division by near-zero)
        # We break and return the closest approximation.
        if vega < 1e-6:
            break
            
        # Newton-Raphson Step
        sigma = sigma - (diff / vega)
        
        # Bound the IV to realistic NSE market limits (0.1% to 300%)
        if sigma <= 0.0:
            sigma = 0.001
        elif sigma > 3.0:
            sigma = 3.0
            
    # Return best guess if max iterations reached without hitting exact tolerance
    return sigma

@njit(fastmath=True, cache=True)
def batch_calculate_iv(spot_prices, strikes, time_to_expiry, risk_free_rate, ltp_array, is_call_array):
    """
    Vectorized function to process the entire option chain in microseconds.
    Takes numpy arrays as inputs and returns an array of IVs.
    """
    n = len(strikes)
    ivs = np.zeros(n)
    for i in range(n):
        ivs[i] = calculate_live_iv(
            spot_prices[i], 
            strikes[i], 
            time_to_expiry[i], 
            risk_free_rate, 
            ltp_array[i], 
            is_call_array[i]
        )
    return ivs

# ── JIT Warm-Up ──
# Compile the Numba functions immediately at startup so the first real tick takes microseconds.
_ = batch_calculate_iv(
    np.array([24000.0, 24000.0]), 
    np.array([24100.0, 23900.0]), 
    np.array([0.01, 0.01]),       
    0.05,                         
    np.array([45.5, 30.2]),       
    np.array([True, False])       
)

def add_live_greeks(df_res):
    if df_res.is_empty():
        return df_res
        
    spots = df_res["spot"].to_numpy().astype(np.float64)
    strikes = df_res["strike"].to_numpy().astype(np.float64)
    
    # INSTITUTIONAL FIX: Numba IV/Spot Sync
    # Spot updates continuously, but LTP only updates on trades. Feeding LTP to Black-Scholes during 
    # fast markets creates artificial IV spikes. We MUST feed the Mid-Price (which is updated instantly by MMs).
    if "bid" in df_res.columns and "ask" in df_res.columns:
        bids = df_res["bid"].to_numpy().astype(np.float64)
        asks = df_res["ask"].to_numpy().astype(np.float64)
        ltps = (bids + asks) / 2.0  # Actually mid_price
    elif "ltp" in df_res.columns:
        ltps = df_res["ltp"].to_numpy().astype(np.float64)
    else:
        ltps = np.zeros(len(spots), dtype=np.float64)
    
    now = datetime.now()
    ts_list = []
    for e in df_res["expiry"].to_list():
        try:
            exp_dt = datetime.strptime(str(e)[:10], "%Y-%m-%d")
            ts_list.append(max((exp_dt - now).total_seconds() / 86400.0 / 365.0, 0.0001))
        except:
            ts_list.append(1.0 / 365.0)
            
    ts = np.array(ts_list, dtype=np.float64)
    rs = np.full(len(spots), 0.07, dtype=np.float64)
    is_calls = (df_res["option_type"] == "CE").to_numpy().astype(np.bool_)
    
    # ── REAL-TIME IV REVERSE-ENGINEERING ──
    # Replaces stale 60-second NSE IV with instantaneous Newton-Raphson IV
    real_time_ivs = batch_calculate_iv(spots, strikes, ts, 0.07, ltps, is_calls)
    
    deltas, gammas, thetas = _vectorized_greeks(spots, strikes, ts, real_time_ivs, rs, is_calls)
    
    return df_res.with_columns([
        pl.Series("iv", real_time_ivs * 100),  # Output in percentage
        pl.Series("delta", deltas),
        pl.Series("gamma", gammas),
        pl.Series("theta", thetas)
    ])


# ── F&O MARKET CLOSE TIME (Updated Aug 2026: derivatives extended to 15:40 IST) ──
FNO_CLOSE_HOUR = 15
FNO_CLOSE_MINUTE = 40

def _parse_expiry_dt(expiry_input):
    """Parse expiry string/datetime and set time to F&O derivatives close (15:40 IST).
    
    Without this, expiry_dt defaults to midnight (00:00) of the expiry date,
    which makes time-to-expiry go negative after midnight on expiry day,
    and understates remaining time value for all BS/Greeks/FVG calculations.
    """
    if isinstance(expiry_input, str):
        try:
            expiry_dt = datetime.strptime(expiry_input, "%Y-%m-%d")
        except Exception:
            return None
    elif isinstance(expiry_input, datetime):
        expiry_dt = expiry_input
    else:
        return None
    
    # Set to F&O derivatives close: 15:40 IST on expiry day
    expiry_dt = expiry_dt.replace(hour=FNO_CLOSE_HOUR, minute=FNO_CLOSE_MINUTE, second=0, microsecond=0)
    return expiry_dt


_live_df_raw = None  # Module-level reference to live tick data, updated each main loop cycle

def lookup_contract_iv(underlying, strike, option_type):
    """
    Compute implied volatility from live tick data.
    1. Check if the live tick buffer has an 'iv' column from the exchange feed.
    2. If not, back-solve IV from the live market price (LTP) using Newton-Raphson.
    Falls back to 15% IV only if no market data is available.
    """
    global _live_df_raw
    
    try:
        if _live_df_raw is not None and not _live_df_raw.is_empty():
            # Try to find the contract in the live tick buffer
            match = _live_df_raw.filter(
                (pl.col("underlying") == underlying) &
                (pl.col("strike") == strike) &
                (pl.col("option_type") == option_type)
            )
            
            if not match.is_empty():
                # Option 1: Exchange-provided IV column
                if "iv" in match.columns:
                    iv_val = match["iv"].last()
                    if iv_val is not None and iv_val > 0:
                        return float(iv_val) / 100.0 if iv_val > 1 else float(iv_val)
                
                # Option 2: Back-solve IV from LTP using Newton-Raphson
                ltp = None
                if "ltp" in match.columns:
                    ltp = match["ltp"].last()
                
                if ltp is not None and ltp > 0:
                    spot_col = "spot" if "spot" in match.columns else None
                    spot = float(match[spot_col].last()) if spot_col and match[spot_col].last() else 0
                    
                    expiry = None
                    if "expiry" in match.columns:
                        expiry = str(match["expiry"].last())
                    
                    if spot > 0 and expiry:
                        solved_iv = _newton_implied_vol(spot, strike, expiry, option_type, float(ltp))
                        if solved_iv is not None:
                            return solved_iv
    except Exception:
        pass
    
    return 0.15  # Ultimate fallback


def _newton_implied_vol(spot, strike, expiry_str, option_type, market_price, r=0.07, max_iter=20, tol=0.001):
    """Newton-Raphson solver to back-out implied volatility from market price."""
    from datetime import datetime
    
    try:
        expiry_dt = _parse_expiry_dt(expiry_str)
        if expiry_dt is None:
            return None
        
        now = datetime.now()
        t = max((expiry_dt - now).total_seconds() / 86400.0 / 365.0, 0.0001)
        
        # Initial guess: start at 20% IV
        iv = 0.20
        is_call = option_type != "PE"
        
        for _ in range(max_iter):
            bs_price = _bs_price_math(spot, strike, t, iv, r, is_call)
            diff = bs_price - market_price
            
            if abs(diff) < tol:
                return iv
            
            # Vega (sensitivity of BS price to IV)
            d1 = (math.log(spot / strike) + (r + (iv ** 2) / 2) * t) / (iv * math.sqrt(t))
            vega = spot * math.sqrt(t) * math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
            
            if vega < 1e-10:
                break
            
            iv = iv - diff / vega
            iv = max(0.01, min(iv, 3.0))  # Clamp IV between 1% and 300%
        
        return iv if 0.01 < iv < 3.0 else None
    except Exception:
        return None


@njit
def _bs_delta_math(spot, strike, t, iv, r, is_call):
    d1 = (math.log(spot / strike) + (r + (iv ** 2) / 2) * t) / (iv * math.sqrt(t))
    call_delta = (1.0 + math.erf(d1 / math.sqrt(2.0))) / 2.0
    if not is_call:
        return call_delta - 1.0
    return call_delta


def approximate_delta(spot, strike, expiry_dt, option_type, iv=None, r=0.07):
    """
    Black-Scholes Delta using actual contract IV from NSE chain.
    iv parameter: decimal (0.18 = 18%). If None, uses 15% fallback.
    """
    if spot <= 0 or strike <= 0:
        return 0.5
    
    if iv is None or iv <= 0:
        iv = 0.15  # fallback only if caller didn't provide
    
    now = datetime.now()
    expiry_dt = _parse_expiry_dt(expiry_dt)
            
    if expiry_dt is not None:
        # Days to expiry (minimum 0.01 days to avoid div by zero)
        t = max((expiry_dt - now).total_seconds() / 86400.0 / 365.0, 0.0001)
    else:
        t = 1.0 / 365.0 # assume 1 day if unknown
        
    return _bs_delta_math(spot, strike, t, iv, r, option_type != "PE")

@njit
def _bs_price_math(spot, strike, t, iv, r, is_call):
    d1 = (math.log(spot / strike) + (r + (iv ** 2) / 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    nd1 = (1.0 + math.erf(d1 / math.sqrt(2.0))) / 2.0
    nd2 = (1.0 + math.erf(d2 / math.sqrt(2.0))) / 2.0
    if is_call:
        return spot * nd1 - strike * math.exp(-r * t) * nd2
    else:
        n_neg_d1 = (1.0 + math.erf(-d1 / math.sqrt(2.0))) / 2.0
        n_neg_d2 = (1.0 + math.erf(-d2 / math.sqrt(2.0))) / 2.0
        return strike * math.exp(-r * t) * n_neg_d2 - spot * n_neg_d1

def fair_price(spot, strike, expiry_dt, option_type, iv=None, r=0.07):
    """Black-Scholes fair option price."""
    if spot <= 0 or strike <= 0:
        return 0.0
    if iv is None or iv <= 0:
        iv = 0.15
    now = datetime.now()
    expiry_dt = _parse_expiry_dt(expiry_dt)
    if expiry_dt is not None:
        # Standard calendar time to F&O close (15:40 IST).
        t = max((expiry_dt - now).total_seconds() / 86400.0 / 365.0, 0.0001)
    else:
        t = 1.0 / 365.0
    return _bs_price_math(spot, strike, t, iv, r, option_type != "PE")

@njit
def _bs_greeks_math(spot, strike, t, iv, r, is_call):
    d1 = (math.log(spot / strike) + (r + (iv ** 2) / 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    
    # Standard normal PDF
    pdf_d1 = math.exp(- (d1 ** 2) / 2.0) / math.sqrt(2.0 * math.pi)
    
    # Gamma
    gamma = pdf_d1 / (spot * iv * math.sqrt(t))
    
    # Vega (usually divided by 100 for 1% change)
    vega = spot * math.sqrt(t) * pdf_d1 / 100.0
    
    # Theta (usually divided by 365 for daily decay)
    nd2 = (1.0 + math.erf(d2 / math.sqrt(2.0))) / 2.0
    n_neg_d2 = (1.0 + math.erf(-d2 / math.sqrt(2.0))) / 2.0
    term1 = -(spot * iv * pdf_d1) / (2 * math.sqrt(t))
    
    if is_call:
        theta = (term1 - r * strike * math.exp(-r * t) * nd2) / 365.0
    else:
        theta = (term1 + r * strike * math.exp(-r * t) * n_neg_d2) / 365.0
        
    # Vanna (dDelta / dVol)
    vanna = -pdf_d1 * (d2 / iv)
    
    # Vomma (Volga) (dVega / dVol) (Scaled because Vega is scaled by 100)
    vomma = vega * (d1 * d2) / iv
    
    # Charm (dDelta / dTime)
    charm = -pdf_d1 * (d2 / (2 * t) - r / (iv * math.sqrt(t)))
    
    # Speed (dGamma / dSpot)
    speed = -(gamma / spot) * (1 + d1 / (iv * math.sqrt(t)))
    
    return gamma, vega, theta, vanna, vomma, charm, speed

def calculate_greeks(spot, strike, expiry_dt, option_type, iv=None, r=0.07):
    """Calculates live Gamma, Vega, Theta, Vanna, Vomma, Charm, Speed."""
    if spot <= 0 or strike <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    if iv is None or iv <= 0:
        iv = 0.15
    now = datetime.now()
    expiry_dt = _parse_expiry_dt(expiry_dt)
    if expiry_dt is not None:
        t = max((expiry_dt - now).total_seconds() / 86400.0 / 365.0, 0.0001)
    else:
        t = 1.0 / 365.0
    return _bs_greeks_math(spot, strike, t, iv, r, option_type != "PE")

@njit

def calculate_delta_score(delta_val):
    """Bell curve scoring for Delta. Peak around 0.45-0.55."""
    abs_d = abs(delta_val)
    if abs_d < 0.20: return 0.2
    if abs_d <= 0.30: return 0.4
    if abs_d <= 0.40: return 0.7
    if abs_d <= 0.60: return 1.0
    if abs_d <= 0.70: return 0.9
    if abs_d <= 0.80: return 0.7
    return 0.4


def compute_entry_window(confidence, gen_dt):
    """Dynamic entry window based on confidence."""
    if confidence >= 0.90:
        window_sec = 180
    elif confidence >= 0.80:
        window_sec = 240
    else:
        window_sec = 300
    return gen_dt, gen_dt + timedelta(seconds=window_sec), window_sec


def compute_expected_hold(exit_style):
    """Expected hold range based on exit style."""
    if exit_style == "TRAIL_2":
        return "2-5 min"
    elif exit_style == "TRAIL_3":
        return "3-8 min"
    return "2-5 min"


def _update_adaptive_state(is_loss, sig=None):
    """Update Adaptive Loss Cooldown state after a trade closes.
    
    Called from update_signal_lifecycle() when a signal transitions to CLOSED.
    - On loss: increment consecutive_losses. If streak >= 2, trigger cooldown.
    - On win: reset consecutive_losses and clear cooldown.
    """
    global consecutive_losses, cooldown_until
    global regime_state
    if is_loss:
        consecutive_losses += 1
        if sig and sig.get("action") == "BUY" and sig.get("generated_at") and sig.get("closed_at"):
            try:
                gen_t = datetime.strptime(sig["generated_at"], "%Y-%m-%d %H:%M:%S")
                cl_t = datetime.strptime(sig["closed_at"], "%Y-%m-%d %H:%M:%S")
                if (cl_t - gen_t).total_seconds() < 600:
                    regime_state["whipsaw_penalty"] += 1
                    regime_state["whipsaw_decay_until"] = time.time() + 1800
                    log.info("WHIPSAW PENALTY INC: %d", regime_state["whipsaw_penalty"])
            except Exception: pass
        if consecutive_losses >= 2:
            cooldown_until = datetime.now() + timedelta(minutes=ALC_COOLDOWN_MINUTES)
            log.info("ALC ACTIVATED: %d consecutive losses. Cooldown until %s",
                     consecutive_losses, cooldown_until.strftime("%H:%M:%S"))
    else:
        if consecutive_losses > 0:
            log.info("ALC RESET: Win after %d consecutive losses", consecutive_losses)
        consecutive_losses = 0
        cooldown_until = None


def _track_direction(option_type):
    """Track published signal direction for Same-Direction Throttle.
    
    Called after a signal is published. Maintains a rolling window of directions.
    If the last SDT_MAX_SAME_SIDE signals are all the same direction,
    triggers a directional cooldown.
    """
    global last_directions, direction_cooldown_until
    last_directions.append(option_type)
    # Keep only last 10 to prevent unbounded growth
    if len(last_directions) > 10:
        last_directions = last_directions[-10:]
    
    # Check if we just hit the throttle limit
    if len(last_directions) >= SDT_MAX_SAME_SIDE:
        recent = last_directions[-SDT_MAX_SAME_SIDE:]
        if all(d == option_type for d in recent):
            direction_cooldown_until = datetime.now() + timedelta(minutes=SDT_COOLDOWN_MINUTES)
            log.info("SDT ACTIVATED: %d consecutive %s trades. Direction cooldown until %s",
                     SDT_MAX_SAME_SIDE, option_type, direction_cooldown_until.strftime("%H:%M:%S"))


def is_executable(row):
    """Pre-publish executability check: premium, spread, volume, cost."""
    now_dt = datetime.now()
    ltp = row.get("ltp", 0) or 0
    bid = row.get("bid", 0) or 0
    ask = row.get("ask", 0) or 0
    vol = row.get("volume", 0) or 0
    underlying = row.get("underlying", "")
    conf = float(row.get("confidence", 0) or 0)
    
    # Entry price
    entry = round((bid + ask) / 2, 2) if (bid > 0 and ask > 0) else ltp
    if entry <= 0:
        return False, "no_price"
        
    # Minimum Premium Check (Ignore deep OTM lottery tickets)
    min_premium = 50 if "NIFTY" in underlying else 80
    if entry < min_premium:
        return False, f"premium_too_low={entry}<{min_premium}"
    
    # ── 5 Sanity Checks (PLAN_MERGED) ──
    # 1. Spread check: 1.5% normal, but allow up to 4.0% for Deep ITM (Mean Reversion)
    if bid > 0 and ask > 0:
        mid = (bid + ask) / 2
        spread_pct = (ask - bid) / mid if mid > 0 else 1.0
        delta_val = row.get("delta") if row.get("delta") is not None else 0.5
        max_spread = 0.04 if abs(delta_val) >= 0.70 else 0.015
        if spread_pct > max_spread:
            return False, f"wide_spread={spread_pct*100:.1f}%>{max_spread*100}%"

    # 2a. Deep ITM ban: delta > 0.95 (Illiquidity and massive bid-ask impact cost)
    # Note: Deep ITM options have almost zero gamma, the true risk here is spread.
    delta_val = row.get("delta") if row.get("delta") is not None else 0.5
    if abs(delta_val) > 0.95:
        return False, f"deep_itm_illiquidity_ban=delta_{delta_val:.2f}>0.95"
    
    # 2b. Fair Value Gap Gate is REMOVED
    # Real-time IV automatically adjusts BS fair value to match market LTP, 
    # ensuring breakouts are never blocked due to stale 60s IV expansions.
    pass
            
    # 2c. Expiry Day Time-of-Day Strike Shift
    # After 12:30 PM on expiry days, restrict current-week contracts (Gamma risk)
    # Allow high-confidence trades through since no next-week shift logic exists
    expiry_str = str(row.get("expiry", ""))
    is_expiry_day = bool(expiry_str and now_dt.strftime("%Y-%m-%d") == expiry_str)
    is_trending = row.get("is_trending", True)
    
    if is_expiry_day:
        now_time = datetime.now().time()
        if now_time.hour > 12 or (now_time.hour == 12 and now_time.minute >= 30):
            # Deep ITM options (Chop Mode) have ~0 Gamma, so they are immune to this risk.
            if conf < 0.70 and is_trending:
                return False, "expiry_shift_ban_current_week_after_1230"
                
    # 2d. NIFTY SELECTIVITY GATE: Nifty momentum trades frequently trap when conviction is marginal.
    # Based on real data: today's Nifty winner had conf=0.7331, loser had conf=0.7178.
    # 0.72 is the clean dividing line. Require conf >= 0.72 for all Nifty trades.
    if "NIFTY" in underlying and "BANK" not in underlying:
        if conf < 0.72:
            return False, f"nifty_low_conviction={conf:.2f}<0.72"
        
    # 3. Directional Checks (Lagging Trend Alignment and Divergence PRUNED)
    option_type = row.get("option_type", "")
    action = row.get("action", "BUY")
    
    if action == "SELL":
        return False, "sell_actions_banned_directional_only"

    # ── TRUE POSITION TRACKING VIA BACKEND LEDGER ──
    # The headless engine writes "TRIGGERED" to the local CSV. To accurately track
    # OPEN vs CLOSED trades, we query the actual backend ledger which tracks real-time PnL.
    real_active_positions = []
    real_closed_signals = []
    accumulated_daily_pnl = 0.0
    
    try:
        resp = httpx.get("http://localhost:4000/api/ledger", timeout=2.0)
        if resp.status_code == 200:
            ledger = resp.json()
            trades = ledger.get("trades", [])
            for t in trades:
                if t.get("status") == "OPEN":
                    real_active_positions.append({
                        "underlying": t.get("underlying"),
                        "option_type": t.get("side")
                    })
                elif t.get("status") == "CLOSED":
                    closed_at = t.get("exitTimestamp") or t.get("timestamp", "")
                    if "T" in str(closed_at):
                        closed_at = closed_at.replace("T", " ").split(".")[0]
                        
                    pnl_pct = 0.0
                    if t.get("netPnl") is not None and t.get("capitalDeployed"):
                        pnl_pct = (t["netPnl"] / t["capitalDeployed"]) * 100
                        
                    real_closed_signals.append({
                        "underlying": t.get("underlying"),
                        "option_type": t.get("side"),
                        "closed_at": closed_at,
                        "pnl_pct": round(pnl_pct, 2),
                        "pnl": float(t.get("netPnl") or 0.0)
                    })
                    
                    # Sync true PnL back to local tracker for dashboard accuracy
                    for sig in all_signals:
                        if (sig["underlying"] == t.get("underlying") and 
                            str(sig.get("strike", "")) == str(t.get("strike", "")) and 
                            sig["option_type"] == t.get("side") and 
                            sig["status"] != "EXPIRED"):
                            
                            sig["status"] = "CLOSED"
                            sig["pnl_pct"] = round(pnl_pct, 2)
                            sig["pnl"] = t.get("netPnl", 0)
                            if not sig.get("closed_at"):
                                sig["closed_at"] = closed_at
                    

                    if closed_at and closed_at.startswith(now_dt.strftime("%Y-%m-%d")):
                        accumulated_daily_pnl += t.get("netPnl", 0)
    except Exception as e:
        log.warning("Failed to fetch real ledger for cooldowns: %s", e)
        
    # 5. RATE LIMITER: Hard cap on trade frequency (fixes machine-gun bug)
    # Checks both entry times AND exit times (real_closed_signals) to prevent chasing
    # a trade 5 seconds after the previous one hit its target.
    
    TRADE_COOLDOWN_MINUTES = 3     # Minimum gap between any two trades (or after an exit)
    MAX_TRADES_PER_WINDOW = 2      # Max trades in the rolling window
    WINDOW_MINUTES = 5             # Rolling window size
    
    recent_events = []
    for s in all_signals:
        if s.get("generated_at"):
            try:
                recent_events.append(datetime.strptime(s["generated_at"], "%Y-%m-%d %H:%M:%S"))
            except: pass
            
    if real_closed_signals:
        for s in real_closed_signals:
            if s.get("closed_at"):
                try:
                    closed_ts = s["closed_at"][:19].replace("T", " ")
                    recent_events.append(datetime.strptime(closed_ts, "%Y-%m-%d %H:%M:%S"))
                except: pass
                
    recent_events = [dt for dt in recent_events if (now_dt - dt).total_seconds() < WINDOW_MINUTES * 60]
    
    # Hard cap: max trades per 5-minute window (only count entries, not exits)
    recent_entries = [
        s for s in all_signals 
        if s.get("generated_at") and 
        (now_dt - datetime.strptime(s["generated_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() < WINDOW_MINUTES * 60
    ]
    if len(recent_entries) >= MAX_TRADES_PER_WINDOW:
        return False, f"rate_limit_max_{MAX_TRADES_PER_WINDOW}_per_{WINDOW_MINUTES}min (recent={len(recent_entries)})"
    
    # Cooldown: minimum 3 minutes between any events (entries OR exits)
    if recent_events:
        last_time = max(recent_events)
        elapsed_sec = (now_dt - last_time).total_seconds()
        if elapsed_sec < TRADE_COOLDOWN_MINUTES * 60:
            remaining = int(TRADE_COOLDOWN_MINUTES * 60 - elapsed_sec)
            return False, f"trade_cooldown_{remaining}s_remaining"
            
    # --- SAFETY CHECKS USING TRUE LEDGER DATA ---
    
    if len(real_active_positions) >= 2:
        return False, "skipped_at_capacity_max_concurrent"
        
    for pos in real_active_positions:
        if pos.get("underlying") == underlying:
            return False, f"position_already_open_on_{underlying}"
            
    # Allow independent trading: don't block BankNifty CE just because a Nifty PE is open.
    # for pos in real_active_positions:
    #     if pos.get("option_type") != option_type:
    #         return False, f"contradictory_position_open_{pos.get('underlying')}_{pos.get('option_type')}"
    
    # Block opposite-direction trades on same underlying within cooldown window (using local recent)
    for s in recent_entries:
        if s.get("underlying") == underlying and s.get("option_type") != option_type:
            return False, f"opposite_direction_cooldown_{s.get('underlying')}_{s.get('option_type')}_vs_{option_type}"

    # ── FIX 1: ANTI FLIP-FLOP COOLDOWN ──────────────────────────────
    # After a losing trade, block the OPPOSITE direction for 5 minutes.
    # Prevents the classic chop pattern: CE loss → immediate PE → PE loss → immediate CE.
    FLIP_FLOP_COOLDOWN = 5 * 60  # 5 minutes
    if real_closed_signals:
        opposite_closed = [
            s for s in real_closed_signals
            if s.get("option_type") != option_type
            and s.get("pnl", 0) < 0
            and s.get("closed_at", "").startswith(now_dt.strftime("%Y-%m-%d"))
        ]
        if opposite_closed:
            last_opp = max(opposite_closed, key=lambda s: s["closed_at"])
            try:
                closed_ts = last_opp["closed_at"][:19].replace("T", " ")
                closed_time = datetime.strptime(closed_ts, "%Y-%m-%d %H:%M:%S")
                elapsed = (now_dt - closed_time).total_seconds()
                if elapsed < FLIP_FLOP_COOLDOWN:
                    remaining = int(FLIP_FLOP_COOLDOWN - elapsed)
                    return False, f"anti_flip_flop_{option_type}_after_{last_opp['option_type']}_loss_{remaining}s"
            except (ValueError, TypeError):
                pass

    # ── SAME-DIRECTION COOLDOWN (15 min for loss, 5 min for win) ──
    LOSS_DIRECTION_COOLDOWN = 15 * 60  
    WIN_DIRECTION_COOLDOWN = 5 * 60
    if real_closed_signals:
        same_direction_closed = [
            s for s in real_closed_signals 
            if s.get("option_type") == option_type
        ]
        if same_direction_closed:
            last_same = max(same_direction_closed, key=lambda s: s["closed_at"])
            try:
                # Handle ISO 8601 with timezone offsets
                closed_ts = last_same["closed_at"][:19].replace("T", " ")
                closed_time = datetime.strptime(closed_ts, "%Y-%m-%d %H:%M:%S")
                elapsed = (now_dt - closed_time).total_seconds()
                
                if last_same.get("pnl", 0) < 0:
                    if elapsed < LOSS_DIRECTION_COOLDOWN:
                        # DYNAMIC JUDGMENT OVERRIDE for losses
                        if conf >= 0.90:
                            pass # Allow the trade, bypass cooldown
                        else:
                            remaining = int(LOSS_DIRECTION_COOLDOWN - elapsed)
                            return False, f"same_direction_loss_cooldown_{option_type}_{remaining}s_remaining"
                else:
                    # Post-win cooldown (prevents chasing a move that already played out)
                    if elapsed < WIN_DIRECTION_COOLDOWN:
                        remaining = int(WIN_DIRECTION_COOLDOWN - elapsed)
                        return False, f"same_direction_win_cooldown_{option_type}_{remaining}s_remaining"
            except (ValueError, TypeError) as e:
                log.warning("Same-direction cooldown timestamp parse failed: %s", e)

    # ── MAX SAME-DIRECTION TRADES PER DAY ──
    MAX_SAME_DIR_PER_DAY = 2
    closed_today = [s for s in real_closed_signals if s.get("closed_at") and s["closed_at"].startswith(now_dt.strftime("%Y-%m-%d"))]
    same_dir_today = [s for s in closed_today if s.get("option_type") == option_type and s.get("underlying") == underlying]
    if len(same_dir_today) >= MAX_SAME_DIR_PER_DAY:
        return False, f"max_{MAX_SAME_DIR_PER_DAY}_same_direction_trades_reached_for_{underlying}_{option_type}"

    # 6. System Health Monitor (Safe Mode) & Daily Max Loss
    # MASTER FIX D: Tightened daily max loss from -5000 to -1500
    current_max_loss = get_dynamic_max_loss()
    if accumulated_daily_pnl < current_max_loss:
        return False, f"daily_max_loss_breached={accumulated_daily_pnl:.0f}<{current_max_loss}"
        
    # Pause trading if >= 3 consecutive losses today
    closed_today.sort(key=lambda x: x["closed_at"])
    
    if len(closed_today) >= 3:
        last_3 = closed_today[-3:]
        if all(s.get("pnl", 0) < 0 for s in last_3):
            return False, "safe_mode_3_consecutive_losses_today"
            
    # --- Strategy-Specific Execution Validation ---
    engine_type = row.get("_engine", "Momentum Breakout")
    
    # 7. Time of Day Filters
    hour, minute = now_dt.hour, now_dt.minute
    if hour == 9 and minute < 45:
        return False, "time_of_day_early_block"
    if hour > 15 or (hour == 15 and minute >= 36):
        return False, "time_of_day_late_block"
        
    # --- Strategy C: Closing Auction / Power Hour Specific Validation ---
    if "POWER_HOUR" in engine_type or "Closing Auction" in engine_type:
        if hour == 15 and minute <= 35:
            if row.get("ltp", 0) > 180:
                return False, f"cas_premium_too_high_{row.get('ltp', 0)}>180"
            if conf < 0.70:
                return False, f"cas_low_conf={conf:.2f}<0.70"
            return True, "PASSED_CAS_STRATEGY_C"
            
    # --- Strategy B: Mean Reversion Specific Validation (BEFORE Momentum gates) ---
    if engine_type == "Mean Reversion":
        # Deep ITM options for theta-immune fades (Delta 0.55 to 0.92, aligned with entry filter)
        abs_d = abs(row.get("delta", 0.75) or 0.75)
        if abs_d < 0.55 or abs_d > 0.92:
            return False, f"mean_rev_delta_out_of_range_{abs_d:.2f}_not_in_[0.55,0.92]"
        if conf < 0.60:
            return False, f"mean_rev_low_conf={conf:.2f}<0.60"
        # Deep ITM premiums are naturally higher — allow up to MAX_BANKNIFTY_PREMIUM / NIFTY 600
        ltp_val = row.get("ltp", 0) or 0
        if underlying == "BANKNIFTY" and ltp_val > MAX_BANKNIFTY_PREMIUM:
            return False, f"mean_rev_banknifty_premium_too_high_{ltp_val:.1f}>{MAX_BANKNIFTY_PREMIUM}"
        elif underlying == "NIFTY" and ltp_val > 600:
            return False, f"mean_rev_nifty_premium_too_high_{ltp_val:.1f}>600"
        return True, "PASSED_MEAN_REVERSION_STRATEGY_B"

    # --- Strategy A: Momentum Breakout Specific Validation ---
    if hour == 14 and minute >= 45:
        if conf < 0.80:
            return False, f"late_session_low_conf={conf:.2f}<0.80"
            
    # --- Premium Sweet Spot Guard for Momentum (only reached by Strategy A) ---
    ltp_val = row.get("ltp", 0) or 0
    if underlying == "BANKNIFTY" and (ltp_val > 650 or ltp_val < 120):
        return False, f"banknifty_premium_out_of_range_{ltp_val:.1f}_not_in_[120,650]"
    elif underlying == "NIFTY" and (ltp_val > 250 or ltp_val < 35):
        return False, f"nifty_premium_out_of_range_{ltp_val:.1f}_not_in_[35,250]"

    # --- P2: Early Session Settling Bar ---
    # Before 10:00 AM, VWAP and OI are highly volatile and regime detection is unstable.
    # Force a higher confidence threshold (0.75+) to prevent false breakouts.
    if hour == 9 and minute >= 45:
        if conf < 0.75:
            return False, f"early_session_low_conf={conf:.2f}<0.75"

    # --- European Open Directional Alignment (12:30 - 13:30 IST) ---
    # Integrates DAX/Europe sentiment to boost confidence or block counter-trend entries during European open
    if (hour == 12 and minute >= 30) or (hour == 13 and minute <= 30):
        euro_sent = macro_cached_data.get("euro_sentiment", "NEUTRAL") if macro_cached_data else "NEUTRAL"
        euro_pct = macro_cached_data.get("euro_pct_change", 0.0) if macro_cached_data else 0.0
        if euro_sent == "BEARISH" and euro_pct <= -0.4:
            if option_type == "CE" and action == "BUY":
                if conf < 0.85:
                    return False, f"euro_bearish_open_blocked_CE (dax={euro_pct:.2f}%)"
        elif euro_sent == "BULLISH" and euro_pct >= 0.4:
            if option_type == "PE" and action == "BUY":
                if conf < 0.85:
                    return False, f"euro_bullish_open_blocked_PE (dax={euro_pct:.2f}%)"
            
    # 9. Global Macro Sentiment Filter
    if macro_cached_data:
        macro_risk = macro_cached_data.get('risk_level', 'LOW')
        macro_override = macro_cached_data.get('regime_override')
        macro_conf_boost = macro_cached_data.get('confidence_boost', 0)
        
        # HIGH RISK: Block all bullish CE trades entirely
        if macro_risk == 'HIGH' and macro_override == 'BEARISH_ONLY':
            if option_type == 'CE' and action == 'BUY':
                return False, f"macro_risk_HIGH_bullish_blocked (score={macro_cached_data.get('macro_risk_score', 0):.3f})"
        
        # ELEVATED/HIGH: Raise minimum confidence requirement
        if macro_conf_boost > 0:
            effective_min_conf = PUBLISH_THRESHOLD + macro_conf_boost
            if conf < effective_min_conf:
                return False, f"macro_confidence_gate={conf:.4f}<{effective_min_conf:.2f} (boost={macro_conf_boost:.2f})"
    
    # 9b. OI-Aligned Directional Confidence Adjustment
    # NSE data removed, oi_net default 0
    oi_net = 0
    oi_conf_adj = 0.0
    if oi_net <= -15:  # Strong BEARISH institutional flow
        if option_type == 'PE':
            oi_conf_adj = +0.03  # Boost PE (aligned with flow)
        elif option_type == 'CE':
            oi_conf_adj = -0.03  # Penalize CE (fighting flow)
    elif oi_net >= 15:  # Strong BULLISH institutional flow
        if option_type == 'CE':
            oi_conf_adj = +0.03  # Boost CE (aligned with flow)
        elif option_type == 'PE':
            oi_conf_adj = -0.03  # Penalize PE (fighting flow)
    
    conf = conf + oi_conf_adj
    if oi_conf_adj != 0:
        log.info("OI_DIRECTIONAL_ADJ: %s %s oi_net=%d adj=%+.2f -> effective_conf=%.4f",
                 underlying, option_type, oi_net, oi_conf_adj, conf)

    # ── ADAPTIVE ALPHA ENGINE v2 ─────────────────────────────────
    # Enforce Dangling Quality Gates
    if conf > MAX_CONFIDENCE:
        return False, f"max_confidence_exceeded_{conf:.2f}>{MAX_CONFIDENCE}"
        
    global latest_spot_directions
    underlying = row.get("underlying", "")
    latest_spot_dir = latest_spot_directions.get(underlying, "NEUTRAL")
    
    # Base confidence threshold
    req_conf = 0.70
    
    # Asymmetric counter-trend penalty: require 0.75+ for trades fighting the macro trend
    if option_type == "CE" and latest_spot_dir == "BEARISH":
        req_conf = 0.75
    elif option_type == "PE" and latest_spot_dir == "BULLISH":
        req_conf = 0.75
        
    if conf < req_conf:
        return False, f"macro_risk_failed_{conf:.2f}<{req_conf}_(regime={latest_spot_dir})"
        
    if underlying == "BANKNIFTY" and ltp > MAX_BANKNIFTY_PREMIUM:
        return False, f"banknifty_premium_too_high_{ltp}>{MAX_BANKNIFTY_PREMIUM}"
    
    # MASTER FIX E: Premium cap for momentum BUY trades
    # High-premium Deep ITM options have low gamma (bad for momentum) and massive absolute risk.
    # Cap is lot-size-aware: NIFTY (lot=65) max ₹450, BANKNIFTY (lot=30) max ₹900.
    max_prem = MAX_MOMENTUM_PREMIUM.get(underlying, 450)
    if action == "BUY" and is_trending and ltp > max_prem:
        return False, f"master_fix_e_premium_cap={ltp:.0f}>{max_prem}_momentum_buy"
    
    # Expiry-Day Detection
    is_expiry_day = False
    expiry_str = str(row.get("expiry", ""))
    if expiry_str and now_dt.strftime("%Y-%m-%d") == expiry_str:
        is_expiry_day = True
        
    # Expiry-day confidence penalty (require +0.05 higher conviction)
    if is_expiry_day and conf < 0.55:
        return False, f"expiry_day_low_conf={conf:.2f}<0.55"
    
    # 9. Adaptive Loss Cooldown (ALC)
    # After 2 consecutive losing trades, pause for 10 minutes.
    # After cooldown expires, only resume if confidence >= 0.65.
    if cooldown_until is not None:
        if now_dt < cooldown_until:
            return False, f"adaptive_loss_cooldown_until_{cooldown_until.strftime('%H:%M')}"
        else:
            # Cooldown expired — resume only with higher conviction
            if conf < ALC_RESUME_MIN_CONF:
                return False, f"post_cooldown_low_conf={conf:.2f}<{ALC_RESUME_MIN_CONF}"
    
    # 10. Same-Direction Throttle (SDT)
    # After 3 consecutive same-direction trades, pause that direction for 15 minutes.
    # DYNAMIC JUDGMENT OVERRIDE: If confidence is massive (>= 0.70), the trend is undeniable. Do NOT throttle.
    if conf < 0.70:
        if direction_cooldown_until is not None:
            if now_dt < direction_cooldown_until:
                # Check if current signal is the same direction that triggered the throttle
                if last_directions and len(last_directions) >= SDT_MAX_SAME_SIDE:
                    throttled_direction = last_directions[-1]
                    if option_type == throttled_direction:
                        return False, f"same_direction_throttle_{option_type}_until_{direction_cooldown_until.strftime('%H:%M')}"
        
        if len(last_directions) >= SDT_MAX_SAME_SIDE:
            if all(d == option_type for d in last_directions[-SDT_MAX_SAME_SIDE:]):
                return False, f"same_direction_throttle_{SDT_MAX_SAME_SIDE}_consecutive_{option_type}"
    
    # 11. Regime-Aware Confidence Gating (RCG)
    # Dynamically raise confidence bar as daily losses mount.
    daily_realized_pnl = sum(float(s.get("pnl", 0) or 0) for s in closed_today)
    
    if daily_realized_pnl < RCG_DEFENSIVE_THRESHOLD:
        if conf < RCG_DEFENSIVE_MIN_CONF:
            return False, f"rcg_defensive_mode_pnl={daily_realized_pnl:.0f}_conf={conf:.2f}<{RCG_DEFENSIVE_MIN_CONF}"
    elif daily_realized_pnl < RCG_CAUTION_THRESHOLD:
        if conf < RCG_CAUTION_MIN_CONF:
            return False, f"rcg_caution_mode_pnl={daily_realized_pnl:.0f}_conf={conf:.2f}<{RCG_CAUTION_MIN_CONF}"

    return True, "OK"


def compute_option_atr(df_raw, underlying, strike, option_type, period=20):
    """
    Compute a proxy ATR (Average True Range) for a specific option contract
    from the tick buffer. Uses 1-minute bucketed high-low range.
    
    Returns the ATR in absolute price terms, or None if insufficient data.
    """
    if df_raw is None or df_raw.is_empty():
        return None
    
    # Filter to the specific contract
    try:
        df_contract = df_raw.filter(
            (pl.col("underlying") == underlying) &
            (pl.col("strike") == strike) &
            (pl.col("option_type") == option_type)
        )
    except Exception:
        return None
    
    if df_contract.is_empty() or "ltp" not in df_contract.columns or "timestamp" not in df_contract.columns:
        return None
    
    # Bucket into 1-minute candles
    BUCKET_MS = 60_000
    df_contract = df_contract.with_columns(
        (pl.col("timestamp") // BUCKET_MS * BUCKET_MS).alias("bucket")
    )
    
    # Compute high/low/close per bucket
    candles = df_contract.group_by("bucket").agg([
        pl.col("ltp").max().alias("high"),
        pl.col("ltp").min().alias("low"),
        pl.col("ltp").last().alias("close"),
    ]).sort("bucket")
    
    if candles.height < 3:
        return None
    
    # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    highs = candles["high"].to_numpy()
    lows = candles["low"].to_numpy()
    closes = candles["close"].to_numpy()
    
    true_ranges = []
    for i in range(1, len(highs)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        true_ranges.append(max(hl, hc, lc))
    
    if not true_ranges:
        return None
    
    # Use last `period` candles (or all if fewer)
    recent = true_ranges[-period:]
    atr = sum(recent) / len(recent)
    
    # Floor at 0.5% of last LTP to prevent absurdly tight stops on stale data
    last_ltp = float(closes[-1])
    if last_ltp > 0:
        atr = max(atr, last_ltp * 0.005)
    
    return round(atr, 2)


def build_trade_idea(row, gen_dt, df_latest=None, df_raw=None):
    """Convert a scored row into a slippage-aware trade idea dict."""
    ltp = row.get("ltp", 0) or 0
    bid = row.get("bid", 0) or 0
    ask = row.get("ask", 0) or 0
    underlying = row.get("underlying", "")
    option_type = row.get("option_type", "")
    
    action = row.get("action", "BUY")
    confidence = round(row.get("confidence", 0), 4)
    spread = round(ask - bid, 2) if (bid > 0 and ask > 0) else 0
    penalties = row.get("penalties", []) if isinstance(row.get("penalties", []), list) else []
    dominant_feature = row.get("dominant_feature", "")
    feature_contributions = row.get("feature_contributions", {})
    
    if action == "SELL":
        return None
        
    strike_val = row.get("strike", 0)
    
    # ── ANTI-CHASING GUARD ────────────────────────────────────────
    # If the option price has already spiked > 6% above its 3-bar moving average,
    # the breakout wick is over-extended. Block entry to prevent buying at the peak!
    price_vel = row.get("price_velocity", 0) or 0
    if price_vel > 0.06:
        log.warning("build_trade_idea dropped %s %s %s: Anti-chasing guard (price_vel=%.3f > 0.06)",
                    underlying, strike_val, option_type, price_vel)
        return None

    # ── Pullback Limit Entry Pricing ─────────────────────────────
    # Instead of buying at the Ask (top of the spread/wick), we place a strict limit
    # order at a discount (near the Bid) to force a pullback entry.
    base_price = ask if ask > 0 else (ltp if ltp > 0 else 0)
    if base_price <= 0:
        log.warning("build_trade_idea silently dropped %s %s %s: base_price is 0", underlying, strike_val, option_type)
        return None
        
    # Set limit entry price at a discount (Bid + 25% of spread) instead of peak Ask
    if bid > 0 and ask > 0 and ask > bid:
        entry = round(bid + (ask - bid) * 0.25, 2)
    else:
        pullback_pct = 0.005 if row.get("is_trending") else 0.0025
        entry = round(base_price * (1 - pullback_pct), 2)
        
    max_entry = entry
        
    # Cost-aware stop and targets (based on ENTRY, not stale price)
    lot = LOT_SIZE.get(underlying, 65)
    cost_per_unit = ROUND_TRIP_COST / lot
    min_target_move = cost_per_unit * 3
    
    # ── REGIME-ADAPTIVE TP/SL & VOLATILITY SCALING ───────────────
    # Detect market regime from the row's features (already computed)
    # Use regime_confidence for primary trending gauge, fallback to momentum
    vol_regime = row.get("volatility_regime", 0.5)
    momentum = abs(row.get("momentum_5", 0) or 0)
    reg_conf = row.get("regime_confidence", 40)
    
    # Scale TP/SL dynamically by Implied Volatility
    iv = row.get("iv", 15.0)
    iv_scale = max(0.7, min(1.4, math.sqrt(iv / 15.0)))
    
    # Regime classification:
    is_trending = row.get("is_trending")
    if is_trending is None:
        is_trending = reg_conf > 60 or momentum > 0.012
    
    delta_raw = row.get("delta")
    delta_val = abs(delta_raw) if delta_raw is not None else 0.5
    if delta_val == 0: delta_val = 0.5
    
    underlying_price = row.get("spot", 0)
    if not underlying_price or underlying_price <= 0:
        underlying_price = row.get("underlying_price", 0)
    if not underlying_price or underlying_price <= 0:
        # Fallback approximation if spot price is missing entirely
        underlying_price = 24000 if underlying == "NIFTY" else 50000

    # Expiry-Day Detection
    # Note: Using literal contract expiry_str matches exactly, regardless of Thursday (Nifty) or Wednesday (BankNifty)
    is_expiry_day = False
    expiry_str = str(row.get("expiry", ""))
    if expiry_str and gen_dt.strftime("%Y-%m-%d") == expiry_str:
        is_expiry_day = True
    
    # MASTER FIX: Regime-Decoupled Exit Logic (No Scalps)
    # All regimes capture open-ended runners using IV-scaled trailing stops.
    exit_style = "TRAIL_MAX"
    
    # Adjustment 4: Asymmetric Gamma Trailing
    if is_expiry_day and (gen_dt.hour > 12 or (gen_dt.hour == 12 and gen_dt.minute >= 30)):
        exit_style = "GAMMA_TRAIL"
        log.info(f"Engaging GAMMA_TRAIL for {underlying} on Expiry Day Post-12:30PM")
    
    underlying = row.get("underlying", "")
    current_regime = current_regimes.get(underlying, "CHOPPY_MEAN_REVERSION")
    
    # ── ATR-BASED ADAPTIVE TP/SL ────────────────────────────────
    # Instead of computing stops from underlying spot price (which was giving
    # Rs 7 stops on Rs 200 options), compute from the option's own price action.
    strike_val = row.get("strike", 0)
    option_atr = compute_option_atr(df_raw, underlying, strike_val, option_type)
    
    if option_atr and option_atr > 0:
        # ATR available: use it for adaptive stops
        sl_mult = 3.5
        if current_regime == "CHOPPY_MEAN_REVERSION":
            sl_mult = 2.5     # Tighter 2.5x ATR stop for choppy scalps
            tp_mult_1 = 1.0   # Quick 1.0R scalp target (mean reversion to VWAP)
            tp_mult_2 = 1.5   # 1.5R secondary scalp target
        elif current_regime in ("PANIC_BEAR", "PANIC_BULL"):
            sl_mult = 4.0     # Wider stop for panic moves
            tp_mult_1 = 3.0
            tp_mult_2 = 5.0
        else:
            # TRENDING_MOMENTUM
            tp_mult_1 = 2.0
            tp_mult_2 = 3.5
        
        stop_dist = round(option_atr * sl_mult, 2)
        
        log.info("ATR_STOPLOSS: %s %s %s | ATR=%.2f | SL_dist=%.2f (%.1f%% of entry) | regime=%s",
                 underlying, strike_val, option_type, option_atr, stop_dist,
                 stop_dist / entry * 100 if entry > 0 else 0, current_regime)
    else:
        # Fallback: percentage-based stops when ATR data is insufficient
        if current_regime == "CHOPPY_MEAN_REVERSION":
            sl_pct = 0.045  # 4.5% tight stop for choppy scalps
            tp_mult_1 = 1.0
            tp_mult_2 = 1.5
        elif current_regime in ("PANIC_BEAR", "PANIC_BULL"):
            sl_pct = 0.10   # 10% stop for panic
            tp_mult_1 = 2.0
            tp_mult_2 = 3.0
        else:
            sl_pct = 0.08   # 8% stop for trending
            tp_mult_1 = 2.0
            tp_mult_2 = 3.5
        
        stop_dist = round(entry * sl_pct, 2)
        log.info("FALLBACK_STOPLOSS: %s %s %s | SL_dist=%.2f (%.1f%% of entry) | No ATR data",
                 underlying, strike_val, option_type, stop_dist, sl_pct * 100)
    
    # Clamp: Stop distance floor scales by premium level.
    # Expensive ATM options (>₹600) use 3.5% (~32+ pts on BankNifty = ₹960 risk) to fit under ₹1200 cap.
    if entry > 600:
        min_stop_pct = 0.035  # 3.5% floor for high-premium options (>₹600)
    elif entry > 300:
        min_stop_pct = 0.045  # 4.5% floor for ATM/ITM (₹300-600)
    elif entry > 100:
        min_stop_pct = 0.06   # 6% floor for near-the-money
    else:
        min_stop_pct = 0.10   # 10% floor for cheap OTM
    
    min_stop = round(entry * min_stop_pct, 2)
    max_stop_pct = 0.08 if current_regime == "CHOPPY_MEAN_REVERSION" else 0.30
    max_stop = round(entry * max_stop_pct, 2)
    stop_dist = max(min_stop, min(stop_dist, max_stop))
    
    if current_regime == "CHOPPY_MEAN_REVERSION":
        # Ultra-fast breakeven lock for choppy scalps (0.25R trigger -> lock breakeven +0.5)
        if action == "BUY":
            direction = "LONG_CE" if option_type == "CE" else "LONG_PE"
            stop = round(entry - stop_dist, 2)
            trail_trigger = round(entry + stop_dist * 0.25, 2)
            trail_target_price = round(entry + 0.5, 2)
        else:
            direction = "SHORT_CE" if option_type == "CE" else "SHORT_PE"
            stop = round(entry + stop_dist, 2)
            trail_trigger = round(entry - stop_dist * 0.25, 2)
            trail_target_price = round(entry - 0.5, 2)
    else:
        # Trending regime: Fractional 0.4R trigger to halve risk (-0.5R)
        if action == "BUY":
            direction = "LONG_CE" if option_type == "CE" else "LONG_PE"
            stop = round(entry - stop_dist, 2)
            trail_trigger = round(entry + stop_dist * 0.4, 2)
            trail_target_price = round(entry - stop_dist * 0.5, 2)
        else:
            direction = "SHORT_CE" if option_type == "CE" else "SHORT_PE"
            stop = round(entry + stop_dist, 2)
            trail_trigger = round(entry - stop_dist * 0.4, 2)
            trail_target_price = round(entry + stop_dist * 0.5, 2)
        
    target1 = round(entry + stop_dist * tp_mult_1, 2) if action == "BUY" else 0.05
    target2 = round(entry + stop_dist * tp_mult_2, 2) if action == "BUY" else 0.05
    risk_per_lot = stop_dist * lot

    stop = max(round(entry * 0.10, 2), stop)
    
    # FIX #13: Proper Fractional Kelly Criterion for position sizing
    # f* = (p * b - q) / b  where p=win_rate, b=avg_win/avg_loss, q=1-p
    # We use HALF Kelly (industry standard for safety) and floor at 0.1
    global consecutive_losses
    
    closed_signals = [s for s in all_signals if s.get("status") == "CLOSED"]
    wins = [s for s in closed_signals if (s.get("pnl_pct", 0) or 0) > 0]
    losses = [s for s in closed_signals if (s.get("pnl_pct", 0) or 0) < 0]
    if len(wins) >= 15 and len(losses) >= 15:
        p = len(wins) / len(closed_signals)
        avg_win = sum(abs(s.get("pnl_pct", 0) or 0) for s in wins) / len(wins)
        avg_loss = sum(abs(s.get("pnl_pct", 0) or 0) for s in losses) / len(losses)
        b = avg_win / (avg_loss + 1e-8)  # payoff ratio
        q = 1 - p
        kelly_f = max(0.0, (p * b - q) / (b + 1e-8))
        # FIX: Hard-cap Kelly at 0.04 to avoid small sample blowups (floor at 0.00 to allow sizing down to 0)
        kelly_multiplier = max(0.00, min(0.04, kelly_f * 0.4))
        log.info("KELLY: p=%.2f b=%.2f f*=%.3f hard_cap_kelly=%.3f", p, b, kelly_f, kelly_multiplier)
    else:
        # Insufficient data — use default that affords at least 1 lot under normal conditions
        kelly_multiplier = 0.035
    
    base_risk_cap = MAX_BUDGET  # Unified risk cap scales against total trading capital
        
    risk_cap = max(int(base_risk_cap * kelly_multiplier), SCALP_STOP_RS)
    
    if risk_per_lot <= 0:
        log.warning("build_trade_idea silently dropped %s %s %s: risk_per_lot <= 0", underlying, strike_val, option_type)
        return None
        
    # ── FIX: QUANTITY SCALED TO STOP_DIST ──
    # If the natural stop is `stop_dist`, how many lots can we buy to exactly risk `SCALP_STOP_RS`?
    max_qty_by_risk = int(SCALP_STOP_RS / stop_dist)
    max_lots_by_risk = max_qty_by_risk // lot
    
    # Also bounded by budget and kelly risk cap
    max_lots = min(max_lots_by_risk, int(risk_cap / risk_per_lot), int(MAX_BUDGET / (entry * lot)))
    
    # Liquidity & Expiry guard: Hard cap lots to prevent illiquid huge sizing
    max_lots_limit = 5 if is_expiry_day else 10
    max_lots = min(max_lots, max_lots_limit)
    
    if max_lots < 1:
        log.warning("build_trade_idea dropped %s %s %s: Stop too wide (%.2f) to afford 1 lot under ₹%d risk limit.", 
                    underlying, strike_val, option_type, stop_dist, SCALP_STOP_RS)
        return None
        
    quantity = max_lots * lot
    
    # ── HARD SCALPING LOGIC INTEGRATION ──
    # User requested: "cap the losses never the profit"
    # We set target points to an unreachable number to ensure we never exit on a hard take-profit,
    # relying entirely on the dynamic trailing stop and EOD exits to let winners run.
    target_points = 50000.0
    
    # Override target
    if action == "BUY":
        target1 = round(entry + target_points, 2)
    else:
        target1 = round(entry - target_points, 2)
    
    log.info("QUANTITY_SIZED: %s %s %s | Risk_Cap=₹%d | Stop_Dist=%.2f | Lots=%d | Target_Pts=%.2f",
             underlying, strike_val, option_type, SCALP_STOP_RS, stop_dist, max_lots, target_points)
    
    # ── TELEMETRY-DRIVEN PENALTIES (Removed as per PLAN_MERGED) ──
    size_mult = 1.0
    effective_confidence = confidence
    
    # Trail target: Halve the risk (move stop to 50% of original distance) to reduce leakage without whipsaw
    if action == "BUY":
        trail_target_price = round(entry - stop_dist * 0.5, 2)
    else:
        trail_target_price = round(entry + stop_dist * 0.5, 2)
    
    # Time-bound fields
    win_start, win_end, win_sec = compute_entry_window(confidence, gen_dt)
    expected_hold = compute_expected_hold(exit_style)
    
    gen_str = gen_dt.strftime("%Y-%m-%d %H:%M:%S")
    win_start_str = win_start.strftime("%H:%M:%S")
    win_end_str = win_end.strftime("%H:%M:%S")
    invalid_after_str = win_end.strftime("%H:%M:%S")
    
    # Extract all numeric indicator features from the scored row
    _skip_keys = {"underlying", "expiry", "strike", "option_type", "ltp", "bid",
                  "ask", "volume", "timestamp", "confidence"}
    feature_dict = {}
    for k, v in row.items():
        if k in _skip_keys:
            continue
        if isinstance(v, (int, float)) and v == v:  # skip NaN
            feature_dict[k] = round(float(v), 6)
    
    # ── Feature Contribution Decomposition (v2.2 telemetry) ──────
    # Maps each scoring signal to its weighted contribution
    # so future analysis can answer: "which feature drove this trade?"
    feature_contributions = {}
    for signal_name, weight in SCORE_WEIGHTS.items():
        raw_val = row.get(signal_name, 0) or 0
        if isinstance(raw_val, (int, float)) and raw_val == raw_val:
            contribution = round(float(raw_val) * weight, 6)
            # Use human-readable names (strip s_ prefix)
            readable = signal_name.replace("s_", "")
            feature_contributions[readable] = contribution
    
    # Dominant feature = highest absolute contribution
    dominant_feature = ""
    if feature_contributions:
        dominant_feature = max(feature_contributions, key=lambda k: abs(feature_contributions[k]))
    
    # Generate unique signal ID to close ML loop later
    signal_id = str(uuid.uuid4())
    
    return {
        "signal_id": signal_id,
        "record_id": row.get("record_id", ""),
        "generated_at": gen_str,
        "telemetry_version": TELEMETRY_VERSION,
        "underlying": row.get("underlying", ""),
        "expiry": str(row.get("expiry", "")),
        "strike": row.get("strike", 0),
        "option_type": row.get("option_type", ""),
        "direction": (
            ("BULLISH" if row.get("option_type") == "CE" else "BEARISH") if action == "BUY" 
            else ("BEARISH" if row.get("option_type") == "CE" else "BULLISH")
        ),
        "last_seen_price": base_price,
        "entry": entry,             # reference entry
        "limit_price": max_entry,   # Explicit limit order with 1% slippage buffer
        "max_entry": max_entry,     # don't chase above this
        "timeout_seconds": 60 if row.get("_engine") == "POWER_HOUR" else (30 if is_trending else 45),
        "quantity": quantity,       # explicit dynamically sized quantity
        "entry_window_start": win_start_str,
        "entry_window_end": win_end_str,
        "invalid_after": invalid_after_str,
        "expected_hold_minutes": expected_hold,
        "stop": stop,
        "stop_type": exit_style,
        "trail_trigger": trail_trigger,
        "trail_target_price": trail_target_price,
        "size_multiplier": max(1, int(max_lots * macro_cached_data.get('position_size_multiplier', 1.0))),
        "target1": target1,
        "target2": target2,
        "strategy": row.get("_engine", "Momentum Breakout") if action == "BUY" else "Credit Spread",
        "regime": "TRENDING" if is_trending else "CHOPPY",
        "confidence": confidence, # Backward compatibility
        "raw_confidence": confidence,
        "effective_confidence": effective_confidence,
        "penalties": penalties,
        "dominant_feature": dominant_feature,
        "feature_contributions": feature_contributions,
        "volume": row.get("volume", 0) or 0,
        "ltp": row.get("ltp", 0) or 0,
        "bid": row.get("bid", 0) or 0,
        "ask": row.get("ask", 0) or 0,
        "spread": spread,
        "status": "LIVE",
        "_win_end_dt": win_end,
        "_features": feature_dict,
        "action": action,
        "hedge_strike": 0,
        "wing_width": 0,
        "risk_per_lot": risk_per_lot,
        "stop_limit_price": round(stop * 1.01, 2) if action == "SELL" else round(stop * 0.99, 2)
    }


def print_trade_banner(idea):
    """Print formatted trade idea banner with slippage-aware pricing."""
    contract = str(idea['underlying']) + " " + str(idea['expiry']) + " " + str(idea['strike']) + " " + str(idea['option_type'])
    lot = LOT_SIZE.get(idea['underlying'], 65)
    lot_cost = round(idea['entry'] * lot)
    last_seen = idea.get('last_seen_price', idea['entry'])
    max_entry = idea.get('max_entry', idea['entry'])
    print()
    print("=" * 50)
    print("  TRADE SIGNAL")
    print("=" * 50)
    print("  " + contract + "  [" + str(idea['direction']) + "]")
    print("-" * 50)
    print("  Last Seen:    Rs." + str(last_seen) + " (data ~30-60s old)")
    print("  LIMIT ORDER:  Rs." + str(idea['entry']) + "  <-- place this")
    print("  DON'T CHASE:  Rs." + str(max_entry) + "  <-- cancel if above")
    print("  Lot Cost:     Rs." + str(lot_cost))
    print("-" * 50)
    print("  Stop Loss:    Rs." + str(idea['stop']) + " (" + str(idea['stop_type']) + ")")
    print("  Target 1:     Rs." + str(idea['target1']))
    print("  Target 2:     Rs." + str(idea['target2']))
    print("-" * 50)
    print("  Confidence:   " + str(idea['confidence']))
    print("  Volume:       " + str(idea['volume']))
    print("  Enter Before: " + str(idea['entry_window_end']))
    print("  Hold:         " + str(idea['expected_hold_minutes']))
    print("=" * 50)
    print()


def send_telegram_alert(idea):
    """Send instant Telegram push notification for a trade signal."""
    try:
        contract = f"{idea['underlying']} {idea['expiry']} {idea['strike']} {idea['option_type']}"
        lot = LOT_SIZE.get(idea['underlying'], 65)
        lot_cost = round(idea['entry'] * lot)
        last_seen = idea.get('last_seen_price', idea['entry'])
        max_entry = idea.get('max_entry', idea['entry'])
        
        hedge_str = ""
        if idea.get('action') == "SELL" and idea.get('hedge_strike'):
            hedge_str = f"🛡️ HEDGE LEG: Buy {idea['underlying']} {idea['expiry']} {idea['hedge_strike']} {idea['option_type']}\n"
            
        msg = (
            f"🚨 *TRADE SIGNAL*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{contract}*\n"
            f"{hedge_str}"
            f"📊 Direction: *{idea['direction']}*\n"
            f"⚙️ Strategy: *{idea.get('strategy', 'Momentum Breakout')}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁 Last Seen: ₹{last_seen}\n"
            f"✅ *LIMIT ORDER: ₹{idea['entry']}*\n"
            f"🚫 Don't Chase: ₹{max_entry}\n"
            f"💰 Lot Cost: ₹{lot_cost:,}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 Stop Loss: ₹{idea['stop']}\n"
            f"🎯 Target 1: ₹{idea['target1']}\n"
            f"🎯 Target 2: ₹{idea['target2']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Confidence: {idea['confidence']}\n"
            f"⏰ Enter Before: {idea['entry_window_end']}\n"
            f"⏳ Hold: {idea['expected_hold_minutes']}"
        )
        
        # 1. FIRE LOCAL WEBHOOK FIRST (0ms Latency for Instant Order Execution)
        try:
            url = "http://localhost:4000/api/signals/webhook"
            webhook_payload = {
                "message": msg,
                "features": {
                    **(idea.get("_features") or {}),
                    "size_multiplier": idea.get("size_multiplier", 1),
                    "confidence": idea.get("confidence", 0),
                    "regime": idea.get("regime", ""),
                    "execution_score": idea.get("execution_score", 0),
                    "timeout_seconds": idea.get("timeout_seconds", 180),
                    "quantity": idea.get("quantity", 0),
                },
                "model_version": idea.get("telemetry_version", ""),
                "strategy_name": idea.get("strategy", ""),
            }
            resp = httpx.post(url, json=webhook_payload, timeout=2.0)
            if resp.status_code == 200:
                log.info("Webhook execution sent instantly for %s", contract)
            else:
                log.warning("Webhook alert failed: %s", resp.text)
        except Exception as e:
            log.warning("Webhook HTTP error: %s", e)

        # 2. FIRE TELEGRAM NOTIFICATION SECOND (Non-blocking for order execution)
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = httpx.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
            }, timeout=5.0)
            
            if resp.status_code == 200:
                log.info("Telegram alert sent for %s", contract)
            else:
                log.warning("Telegram Markdown alert failed (%s), retrying plain text...", resp.text)
                plain_msg = msg.replace("*", "")
                httpx.post(url, json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": plain_msg
                }, timeout=5.0)
        except Exception as e:
            log.warning("Telegram HTTP error: %s", e)
            
    except Exception as e:
        log.warning("Alert/Execution formatting error: %s", e)


def publish_signal(idea):
    """Append trade idea to CSV and send Telegram alert."""
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    file_exists = OUTPUT_CSV.exists()
    
    # Filter out internal fields starting with _
    csv_idea = {k: v for k, v in idea.items() if not k.startswith("_")}
    
    with open(OUTPUT_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_idea.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(csv_idea)
        
    # Week 3: Feature vector collection for future ML
    import json
    ml_log = Path("reports/ml_features_log.jsonl")
    ml_log.parent.mkdir(parents=True, exist_ok=True)
    with open(ml_log, "a") as f:
        # Extract features and full telemetry
        ml_data = idea.get("_features", {}).copy()
        ml_data["signal_id"] = idea.get("signal_id")
        ml_data["target_contract"] = f"{idea.get('underlying')}_{idea.get('strike')}_{idea.get('option_type')}"
        ml_data["timestamp"] = idea.get("generated_at")
        ml_data["regime"] = idea.get("regime")
        ml_data["confidence"] = idea.get("confidence")
        ml_data["action"] = idea.get("action")
        ml_data["hedge_strike"] = idea.get("hedge_strike")
        ml_data["wing_width"] = idea.get("wing_width")
        ml_data["risk_per_lot"] = idea.get("risk_per_lot")
        ml_data["direction"] = idea.get("direction")
        ml_data["limit_price"] = idea.get("limit_price")
        ml_data["stop_loss"] = idea.get("stop")
        
        # Inject new advanced engine telemetry
        telemetry_keys = [
            "selected_delta", "selected_iv", "fair_price", "fair_value_gap", 
            "gamma", "vega", "theta", "vanna", "vomma", "charm", "speed",
            "execution_score", "execution_score_components",
            "selected_reason", "execution_rank", "signal_rank", "total_candidates", "candidate_list"
        ]
        for tk in telemetry_keys:
            if tk in idea:
                ml_data[tk] = idea[tk]
                
        f.write(json.dumps(ml_data) + "\n")
    
    # Send instant Telegram push notification
    send_telegram_alert(idea)


def archive_signal(idea):
    """Append a closed/expired signal to the archive CSV."""
    ARCHIVE_CSV.parent.mkdir(parents=True, exist_ok=True)
    file_exists = ARCHIVE_CSV.exists()
    
    csv_idea = {k: v for k, v in idea.items() if not k.startswith("_")}
    
    with open(ARCHIVE_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_idea.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(csv_idea)


def rewrite_live_csv():
    """Rewrite live CSV with current signal statuses."""
    live_sigs = [s for s in all_signals if s["status"] in ("LIVE", "TRIGGERED")]
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    # Gather all unique keys from all known signals
    csv_fields = []
    for sig in all_signals:
        for k in sig.keys():
            if not k.startswith("_") and k not in csv_fields:
                csv_fields.append(k)
                
    if not live_sigs:
        # Write empty file with header
        if csv_fields:
            with open(OUTPUT_CSV, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields)
                writer.writeheader()
        return
    
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for s in live_sigs:
            writer.writerow({k: v for k, v in s.items() if not k.startswith("_")})


def sync_close_to_backend(sig, exit_price):
    """Notify the Node.js backend ledger to close an open trade in real-time when trailing stop or target is hit."""
    try:
        resp = httpx.get("http://localhost:4000/api/ledger", timeout=2.0)
        if resp.status_code == 200:
            ledger = resp.json()
            for t in ledger.get("trades", []):
                if (t.get("status") == "OPEN" and
                    t.get("underlying") == sig.get("underlying") and
                    float(t.get("strike", 0)) == float(sig.get("strike", 0)) and
                    t.get("side") == sig.get("option_type")):
                    
                    close_payload = {
                        "action": "CLOSE",
                        "tradeId": t.get("id"),
                        "exitPrice": exit_price
                    }
                    httpx.post("http://localhost:4000/api/ledger/trade", json=close_payload, timeout=3.0)
                    log.info("📢 Real-time backend exit sent for %s %s %s @ Rs.%.2f", 
                             sig.get("underlying"), sig.get("strike"), sig.get("option_type"), exit_price)
                    break
    except Exception as e:
        log.warning("Failed to sync backend trade exit: %s", e)


def update_signal_lifecycle(df_raw, df_scored=None):
    """Check all LIVE signals for expiry, trigger, and close conditions."""
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # Get latest prices for option contracts
    df_options = df_raw.filter(
        (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
    ).sort("timestamp")
    
    status_changes = {"expired": 0, "triggered": 0, "closed": 0}
    
    # Sync backend ledger state to clean up un-filled/cancelled pending signals from TUI
    try:
        resp = httpx.get("http://localhost:4000/api/ledger", timeout=1.0)
        if resp.status_code == 200:
            ledger = resp.json()
            backend_trades = ledger.get("trades", [])
            
            for sig in all_signals:
                if sig["status"] == "TRIGGERED":
                    trig_at = sig.get("triggered_at", "")
                    if trig_at:
                        try:
                            trig_dt = datetime.strptime(trig_at[:19], "%Y-%m-%d %H:%M:%S")
                            if (now - trig_dt).total_seconds() > 45:
                                # If 45s passed and trade is NOT open in backend, backend cancelled it
                                is_backend_active = any(
                                    t.get("underlying") == sig["underlying"] and
                                    float(t.get("strike", 0)) == float(sig["strike"]) and
                                    t.get("side") == sig["option_type"]
                                    for t in backend_trades if t.get("status") == "OPEN"
                                )
                                if not is_backend_active:
                                    sig["status"] = "EXPIRED"
                                    sig["expired_at"] = now_str
                                    log.info("TUI_CLEANUP: Removed cancelled pending signal %s %s %s from TUI",
                                             sig["underlying"], sig["strike"], sig["option_type"])
                        except Exception:
                            pass
    except Exception:
        pass
        
    for sig in all_signals:
        if sig["status"] not in ("LIVE", "TRIGGERED"):
            continue
            
        # 1. Expiry check (LIVE only)
        if sig["status"] == "LIVE":
            win_end = sig.get("_win_end_dt")
            if win_end and now > win_end:
                sig["status"] = "EXPIRED"
                sig["expired_at"] = now_str
                archive_signal(sig)
                status_changes["expired"] += 1
                log.info("EXPIRED: %s %s %s", sig["underlying"], sig["strike"], sig["option_type"])
                continue
                
        # 1c. HARD EOD MARKET CLOSE FORCE EXIT (3:37 PM IST)
        # Guarantees zero trades left open past the 3:40 PM F&O market close
        if now.hour == 15 and now.minute >= 37:
            if sig["status"] in ("LIVE", "TRIGGERED"):
                sig["status"] = "CLOSED"
                exit_p = sig.get("last_seen_price", sig["entry"])
                sig["exit_price"] = exit_p
                sig["closed_at"] = now_str
                archive_signal(sig)
                sync_close_to_backend(sig, exit_p)
                status_changes["closed"] += 1
                log.warning("CAS_EOD_FORCED_EXIT: Closing %s %s %s @ Rs.%.2f before 15:40 F&O close", 
                            sig["underlying"], sig["strike"], sig["option_type"], exit_p)
                continue
        
        # 2. Get latest price for this contract
        mask = (
            (df_options["underlying"] == sig["underlying"]) &
            (df_options["expiry"] == sig["expiry"]) &
            (df_options["strike"] == sig["strike"]) &
            (df_options["option_type"] == sig["option_type"])
        )
        df_c = df_options.filter(mask)
        if df_c.is_empty():
            continue
        
        latest = df_c.tail(1).row(0, named=True)
        ltp = latest.get("ltp", 0) or 0
        if ltp <= 0:
            continue
            
        hedge_strike = sig.get("hedge_strike")
        if hedge_strike and sig.get("action") == "SELL":
            hedge_mask = (
                (df_options["underlying"] == sig["underlying"]) &
                (df_options["expiry"] == sig["expiry"]) &
                (df_options["strike"] == float(hedge_strike)) &
                (df_options["option_type"] == sig["option_type"])
            )
            df_hedge = df_options.filter(hedge_mask)
            if not df_hedge.is_empty():
                latest_hedge = df_hedge.tail(1).row(0, named=True)
                hedge_ltp = latest_hedge.get("ltp", 0) or 0
                if hedge_ltp > 0:
                    ltp = round(ltp - hedge_ltp, 2)
        
        entry = sig["entry"]
        stop = sig["stop"]
        t1 = sig["target1"]
        
        # 3. Trigger check (LIVE -> TRIGGERED)
        if sig["status"] == "LIVE":
            # Price near entry = triggered
            if abs(ltp - entry) / entry < 0.02:
                sig["status"] = "TRIGGERED"
                sig["triggered_at"] = now_str
                sig["trigger_price"] = ltp
                status_changes["triggered"] += 1
                log.info("TRIGGERED: %s %s %s @ Rs.%.2f", sig["underlying"], sig["strike"], sig["option_type"], ltp)
        
        # 4. Close check (TRIGGERED -> CLOSED)
        if sig["status"] == "TRIGGERED":
            trigger_price = sig.get("trigger_price", entry)
            action = sig.get("action", "BUY")
            
            # Trailing stop: track peak (or trough for short)
            if action == "BUY":
                peak = sig.get("_peak_price", trigger_price)
                if ltp > peak:
                    sig["_peak_price"] = ltp
                    peak = ltp
            else:
                peak = sig.get("_peak_price", trigger_price)
                if ltp < peak:
                    sig["_peak_price"] = ltp
                    peak = ltp
            
            # Calibrated breakeven & trailing: lock breakeven at 0.25R, trail dynamically past 0.5R
            current_risk = abs(trigger_price - stop)
            target_dist = abs(t1 - trigger_price)
            underlying = sig.get("underlying", "")
            current_regime = current_regimes.get(underlying, "CHOPPY_MEAN_REVERSION")
            
            be_mult = 0.25 if current_regime == "CHOPPY_MEAN_REVERSION" else 0.4
            be_trigger = min(current_risk * be_mult, target_dist * be_mult) if target_dist > 0 else current_risk * be_mult
            
            trail_stop = stop
            overrides = get_trail_overrides()
            is_tight = overrides.get(sig.get("id")) == "tight"
            
            if action == "BUY":
                if is_tight:
                    # Move stop to breakeven immediately, or tightly trail peak
                    trail_stop = max(trail_stop, trigger_price, peak - current_risk * 0.2)
                    
                # Lock breakeven as soon as peak reaches breakeven trigger
                if peak >= trigger_price + be_trigger:
                    trail_stop = max(trail_stop, trigger_price)
                
                # Dynamic peak trailing: past 0.5R, trail 0.4R behind peak to lock 60% of peak gains!
                if current_regime == "CHOPPY_MEAN_REVERSION" and peak >= trigger_price + current_risk * 0.5:
                    trail_stop = max(trail_stop, peak - current_risk * 0.4)
                elif peak >= trigger_price + current_risk * 1.2:
                    trail_stop = max(trail_stop, peak - current_risk * 0.8)
            else:
                if is_tight:
                    trail_stop = min(trail_stop, trigger_price, peak + current_risk * 0.2)
                    
                if peak <= trigger_price - be_trigger:
                    trail_stop = min(trail_stop, trigger_price)
                if current_regime == "CHOPPY_MEAN_REVERSION" and peak <= trigger_price - current_risk * 0.5:
                    trail_stop = min(trail_stop, peak + current_risk * 0.4)
                elif peak <= trigger_price - current_risk * 1.2:
                    trail_stop = min(trail_stop, peak + current_risk * 0.8)
                    
            # PnL Calculation helper
            def calc_pnl(exit_price):
                if action == "BUY":
                    pnl = exit_price - trigger_price
                else:
                    pnl = trigger_price - exit_price
                pct = round(pnl / trigger_price * 100, 2)
                abs_pnl = round(pnl * sig.get("quantity", LOT_SIZE.get(sig["underlying"], 65)), 2)
                return pct, abs_pnl

            is_stopped = (ltp <= trail_stop) if action == "BUY" else (ltp >= trail_stop)
            is_target = (ltp >= t1) if action == "BUY" else (ltp <= t1)

            # Hit stop
            if is_stopped:
                sig["status"] = "CLOSED"
                sig["closed_at"] = now_str
                sig["exit_price"] = ltp
                sig["pnl_pct"], sig["pnl"] = calc_pnl(ltp)
                archive_signal(sig)
                sync_close_to_backend(sig, ltp)
                status_changes["closed"] += 1
                log.info("CLOSED (stop): %s %s %s @ Rs.%.2f pnl=%.2f%%",
                         sig["underlying"], sig["strike"], sig["option_type"], ltp, sig["pnl_pct"])
                # ALC: Track consecutive losses
                _update_adaptive_state(is_loss=True, sig=sig)
            
            # Hit T1
            elif is_target:
                sig["status"] = "CLOSED"
                sig["closed_at"] = now_str
                sig["exit_price"] = ltp
                sig["pnl_pct"], sig["pnl"] = calc_pnl(ltp)
                archive_signal(sig)
                sync_close_to_backend(sig, ltp)
                status_changes["closed"] += 1
                log.info("CLOSED (target): %s %s %s @ Rs.%.2f pnl=%.2f%%",
                         sig["underlying"], sig["strike"], sig["option_type"], ltp, sig["pnl_pct"])
                # ALC: Track consecutive wins (reset streak)
                _update_adaptive_state(is_loss=False, sig=sig)
            
            # Hit Time-Based Early Exits
            elif sig.get("triggered_at"):
                trig_time_str = sig.get("triggered_at", "")
                try:
                    trig_ts = datetime.strptime(trig_time_str.replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                    elapsed_trig_sec = (now - trig_ts).total_seconds()
                    
                    # 1. Stale Choppy Scalp (3 min max hold if bleeding)
                    if current_regime == "CHOPPY_MEAN_REVERSION" and elapsed_trig_sec >= 180 and trail_stop == stop:
                        curr_pct, curr_pnl = calc_pnl(ltp)
                        if curr_pct <= 0.2:
                            sig["status"] = "CLOSED"
                            sig["closed_at"] = now_str
                            sig["exit_price"] = ltp
                            sig["pnl_pct"], sig["pnl"] = curr_pct, curr_pnl
                            archive_signal(sig)
                            sync_close_to_backend(sig, ltp)
                            status_changes["closed"] += 1
                            log.info("CLOSED (stale_choppy_time_exit): %s %s %s @ Rs.%.2f after %ds",
                                     sig["underlying"], sig["strike"], sig["option_type"], ltp, int(elapsed_trig_sec))
                            continue
                            
                    # 2. Stale Momentum Breakout (90 min max hold)
                    elif sig.get("_engine") == "Momentum Breakout" and elapsed_trig_sec >= 90 * 60:
                        sig["status"] = "CLOSED"
                        sig["closed_at"] = now_str
                        sig["exit_price"] = ltp
                        sig["pnl_pct"], sig["pnl"] = calc_pnl(ltp)
                        archive_signal(sig)
                        sync_close_to_backend(sig, ltp)
                        status_changes["closed"] += 1
                        log.info("CLOSED (stale_momentum_time_exit >90m): %s %s %s @ Rs.%.2f after %ds pnl=%.2f%%",
                                 sig["underlying"], sig["strike"], sig["option_type"], ltp, int(elapsed_trig_sec), sig["pnl_pct"])
                        _update_adaptive_state(is_loss=(sig["pnl_pct"] < 0), sig=sig)
                        continue
                except Exception:
                    pass
            
            # Hit Signal Decay Early Exit
            elif df_scored is not None and not df_scored.is_empty():
                mask_scored = (
                    (df_scored["underlying"] == sig["underlying"]) &
                    (df_scored["expiry"] == sig["expiry"]) &
                    (df_scored["strike"] == sig["strike"]) &
                    (df_scored["option_type"] == sig["option_type"])
                )
                df_sc = df_scored.filter(mask_scored)
                if not df_sc.is_empty():
                    latest_sc = df_sc.tail(1).row(0, named=True)
                    comp_alpha = latest_sc.get("composite_alpha_score", 0)
                    if comp_alpha < 0:
                        decay_ticks = sig.get("_decay_ticks", 0) + 1
                        sig["_decay_ticks"] = decay_ticks
                        
                        if decay_ticks >= 2:
                            sig["status"] = "CLOSED"
                            sig["closed_at"] = now_str
                            sig["exit_price"] = ltp
                            sig["pnl_pct"], sig["pnl"] = calc_pnl(ltp)
                            archive_signal(sig)
                            sync_close_to_backend(sig, ltp)
                            status_changes["closed"] += 1
                            log.info("CLOSED (Signal Decay): %s %s %s @ Rs.%.2f pnl=%.2f%% (alpha=%.2f, ticks=%d)",
                                     sig["underlying"], sig["strike"], sig["option_type"], ltp, sig["pnl_pct"], comp_alpha, decay_ticks)
                            _update_adaptive_state(is_loss=(sig["pnl_pct"] < 0), sig=sig)
                    else:
                        sig["_decay_ticks"] = 0

            # Hit Stale Trade Early Exit (5 min max hold for un-trailed stagnant trades)
            if sig["status"] == "TRIGGERED":
                trig_time_str = sig.get("triggered_at", "")
                if trig_time_str:
                    try:
                        trig_ts = datetime.strptime(trig_time_str.replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                        elapsed_trig_sec = (now - trig_ts).total_seconds()
                        # If 5+ mins elapsed, no progress (curr_pct <= 0.2%), and breakeven not locked yet
                        if elapsed_trig_sec >= 300 and trail_stop == stop:
                            curr_pct, curr_pnl = calc_pnl(ltp)
                            if curr_pct <= 0.2:
                                sig["status"] = "CLOSED"
                                sig["closed_at"] = now_str
                                sig["exit_price"] = ltp
                                sig["pnl_pct"], sig["pnl"] = curr_pct, curr_pnl
                                archive_signal(sig)
                                sync_close_to_backend(sig, ltp)
                                status_changes["closed"] += 1
                                log.info("CLOSED (Stale Trade 5min): %s %s %s @ Rs.%.2f pnl=%.2f%%",
                                         sig["underlying"], sig["strike"], sig["option_type"], ltp, sig["pnl_pct"])
                                _update_adaptive_state(is_loss=(curr_pct < 0), sig=sig)
                    except Exception as e:
                        pass
    
    return status_changes


def print_status_dashboard():
    """Print signal lifecycle dashboard."""
    live = [s for s in all_signals if s["status"] == "LIVE"]
    expired = [s for s in all_signals if s["status"] == "EXPIRED"]
    triggered = [s for s in all_signals if s["status"] == "TRIGGERED"]
    closed = [s for s in all_signals if s["status"] == "CLOSED"]
    
    print()
    print("------- SIGNAL DASHBOARD -------")
    print("  ACTIVE:    " + str(len(live)))
    print("  TRIGGERED: " + str(len(triggered)))
    print("  EXPIRED:   " + str(len(expired)))
    print("  CLOSED:    " + str(len(closed)))
    
    if live:
        print("  -- Active Signals --")
        for s in live:
            print("    " + s["underlying"] + " " + str(s["strike"]) + " " + s["option_type"] +
                  " | Rs." + str(s["entry"]) + " | conf=" + str(s["confidence"]) +
                  " | valid until " + str(s["invalid_after"]))
    
    if triggered:
        print("  -- Triggered Signals --")
        for s in triggered:
            print("    " + s["underlying"] + " " + str(s["strike"]) + " " + s["option_type"] +
                  " | entry=Rs." + str(s.get("trigger_price", s["entry"])) +
                  " | triggered=" + str(s.get("triggered_at", "")))
    
    if closed:
        print("  -- Closed Signals --")
        for s in closed[-5:]:  # last 5
            print("    " + s["underlying"] + " " + str(s["strike"]) + " " + s["option_type"] +
                  " | pnl=" + str(s.get("pnl_pct", 0)) + "%" +
                  " | closed=" + str(s.get("closed_at", "")))
    
    # Verify: no expired signal remains LIVE
    stale = [s for s in all_signals if s["status"] == "LIVE" and
             s.get("_win_end_dt") and datetime.now() > s["_win_end_dt"]]
    if stale:
        print("  WARNING: " + str(len(stale)) + " stale LIVE signals!")
    else:
        print("  INTEGRITY: No expired signal remains LIVE")
    
    print("--------------------------------")
    print()
    
    return len(live), len(expired), len(triggered), len(closed)


def send_telegram_message(text):
    """Send a plain text Telegram message."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=5)
        if resp.status_code == 200:
            log.info("Telegram message sent")
    except Exception as e:
        log.warning("Telegram message error: %s", e)

def check_daily_trade_limit():
    """Query the ledger to see how many trades we've taken today."""
    try:
        resp = httpx.get("http://localhost:4000/api/ledger", timeout=2.0)
        if resp.status_code == 200:
            ledger = resp.json()
            today_str = datetime.now().strftime("%Y-%m-%d")
            trades_today = [t for t in ledger.get("trades", []) if t.get("timestamp", "").startswith(today_str)]
            return len(trades_today)
    except Exception as e:
        log.warning("Failed to check daily trade limit: %s", e)
    return 0


import socket
udp_buffer = []
udp_lock = threading.Lock()

def udp_listener_thread():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5005))
    while True:
        try:
            data, _ = sock.recvfrom(65536)
            tick = json.loads(data.decode('utf-8'))
            with udp_lock:
                udp_buffer.append(tick)
                # Hard cap buffer at 800k ticks (approx 20 mins in high volatility) to prevent memory crash
                if len(udp_buffer) > 800000:
                    del udp_buffer[:100000]
        except Exception as e:
            log.error(f"UDP Error: {e}")

def get_udp_dataframe():
    with udp_lock:
        if not udp_buffer:
            return None
        # Copy buffer to release lock instantly, preventing UDP starvation
        raw_data = udp_buffer[:]
        
    df = pl.DataFrame(raw_data)
    if "source_file" not in df.columns:
        df = df.with_columns(pl.lit("udp_stream").alias("source_file"))
    # CRITICAL: Only use data from the last ROLLING_CONTEXT_MINUTES to prevent stale prices
    if "timestamp" in df.columns and not df.is_empty():
        cutoff_ms = time.time() * 1000 - ROLLING_CONTEXT_MINUTES * 60 * 1000
        df = df.filter(pl.col("timestamp") >= cutoff_ms)
        if df.is_empty():
            return None
    return df

def seed_ib_from_today_parquet():
    """Scans Parquet files written TODAY since 9:15 AM to accurately calculate IB High/Low."""
    if not RAW_DIR.exists():
        return
    files = sorted(glob.glob(str(RAW_DIR / "*.parquet")), key=lambda f: os.path.getmtime(f))
    if not files:
        return
    # Filter files modified in the last 8 hours
    cutoff_time = time.time() - 8 * 3600
    today_files = [f for f in files if os.path.getmtime(f) >= cutoff_time]
    if not today_files:
        return
    try:
        df = pl.scan_parquet(today_files).filter(pl.col("strike") == 0.0).collect()
        if not df.is_empty():
            # Fix: Index spot ticks store price in 'ltp' while 'spot' is 0.0
            spot_col = "spot" if "spot" in df.columns else "ltp"
            ltp_col = "ltp" if "ltp" in df.columns else spot_col
            df = df.with_columns(
                pl.when(pl.col(spot_col) > 0).then(pl.col(spot_col)).otherwise(pl.col(ltp_col)).alias("_spot_val")
            )
            # Normalize underlying: >40000 is BANKNIFTY, else NIFTY
            df = df.with_columns(
                pl.when(pl.col("_spot_val") > 40000).then(pl.lit("BANKNIFTY"))
                .otherwise(pl.lit("NIFTY"))
                .alias("underlying")
            )
            df = df.with_columns(pl.from_epoch("timestamp", time_unit="ms").dt.truncate("1m").alias("_minute"))
            df = df.with_columns((pl.col("_minute") + pl.duration(hours=5, minutes=30)).alias("_minute_ist"))
            df_ib = df.filter(
                ((pl.col("_minute_ist").dt.hour() == 9) & (pl.col("_minute_ist").dt.minute() >= 15)) |
                ((pl.col("_minute_ist").dt.hour() == 10) & (pl.col("_minute_ist").dt.minute() <= 15))
            )
            if not df_ib.is_empty():
                for u in ["NIFTY", "BANKNIFTY"]:
                    u_df = df_ib.filter(pl.col("underlying") == u)
                    if not u_df.is_empty():
                        h = float(u_df["_spot_val"].max())
                        l = float(u_df["_spot_val"].min())
                        cached_ib_high[u] = h
                        cached_ib_low[u] = l
                        log.info(f"PERFECT IB SEED [{u}]: High={h:.2f}, Low={l:.2f}")
    except Exception as e:
        log.error(f"Failed to seed IB from parquet: {e}")

def seed_udp_buffer_from_parquet():
    seed_ib_from_today_parquet()
    if not RAW_DIR.exists():
        return
    files = sorted(glob.glob(str(RAW_DIR / "*.parquet")), key=lambda f: os.path.getmtime(f))
    if not files:
        return
    # Only seed from the last ROLLING_CONTEXT_MINUTES worth of files to prevent stale data
    cutoff_time = time.time() - ROLLING_CONTEXT_MINUTES * 60
    recent_files = [f for f in files if os.path.getmtime(f) >= cutoff_time]
    if not recent_files:
        # At minimum, load the last 5 files
        recent_files = files[-5:]
    try:
        df = pl.scan_parquet(recent_files).collect()
        ticks = df.to_dicts()
        with udp_lock:
            udp_buffer.extend(ticks)
        log.info("Seeded UDP buffer with %d ticks from %d recent files", len(ticks), len(recent_files))
    except Exception as e:
        log.error(f"Failed to seed UDP from parquet: {e}")

def load_published_contracts():
    """Load published contracts from disk. Start fresh every day to allow trading the same strike on consecutive days."""
    p = Path("reports/published_contracts.json")
    if p.exists():
        # Clear the cache on startup so we start fresh each day
        try:
            p.unlink()
            log.info("Cleared published_contracts cache for new session.")
        except Exception:
            pass
    return set()

def save_published_contracts():
    """Persist published contracts to disk."""
    p = Path("reports/published_contracts.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    import json
    p.write_text(json.dumps([list(k) for k in published_contracts]))

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase O3A — Live Options Runner")
    parser.add_argument("--ignore-market-hours", action="store_true", help="Keep runner active outside market hours")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args, _ = parser.parse_known_args()

    global seen_files, DATE_STR, RAW_DIR
    if args.date:
        DATE_STR = args.date
        RAW_DIR = Path(f"data/raw/{DATE_STR}")

    log.info("=" * 60)
    log.info("AUTO EXECUTION PIPELINE STARTED")
    log.info("Date: %s", DATE_STR)
    log.info("Raw dir: %s", RAW_DIR)
    log.info("Publish threshold: %s", PUBLISH_THRESHOLD)
    log.info("Poll interval: %ss", POLL_INTERVAL_SEC)
    log.info("=" * 60)
    
    # Send market open notification
    send_telegram_message(
        "🟢 *MARKET SCANNER ONLINE*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date: {DATE_STR}\n"
        f"📊 Scanning: NIFTY + BANKNIFTY\n"
        f"⚡ Flush: 15s | Poll: {POLL_INTERVAL_SEC}s\n"
        f"🎯 Threshold: {PUBLISH_THRESHOLD}\n"
        f"💰 Budget: ₹{MAX_BUDGET:,}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "You'll get a ping only when a trade fires. 🔔"
    )
    
    # Start UDP listener thread
    threading.Thread(target=udp_listener_thread, daemon=True).start()
    
    # ── Pre-Market Macro Sentiment Check ──────────────────────────
    try:
        from market.macro_sentiment import fetch_macro_data, format_macro_telegram_alert
        global macro_cached_data, macro_last_refresh
        macro_cached_data = fetch_macro_data()
        macro_last_refresh = time.time()
        
        # Send macro report to Telegram
        macro_msg = format_macro_telegram_alert(macro_cached_data)
        send_telegram_message(macro_msg)
        if macro_cached_data.get('risk_level') == 'HIGH':
            log.warning("MACRO RISK HIGH (%.3f): Only bearish/PE trades will be allowed!",
                       macro_cached_data['macro_risk_score'])
        elif macro_cached_data.get('risk_level') == 'ELEVATED':
            log.warning("MACRO RISK ELEVATED (%.3f): Confidence requirements tightened.",
                       macro_cached_data['macro_risk_score'])
        else:
            log.info("MACRO RISK LOW (%.3f): Normal trading mode.",
                    macro_cached_data['macro_risk_score'])
    except Exception as e:
        log.warning("Macro sentiment check failed (non-fatal): %s", e)
        macro_cached_data = {}
    
    # Initialize with existing files to populate historical rolling context
    existing = get_parquet_files()
    if existing:
        log.info("Found %d existing parquet files", len(existing))
        seen_files = set(existing)
        seed_udp_buffer_from_parquet()
    else:
        log.info("No existing parquets. Starting fresh...")
    
    # Load published contracts from disk to prevent duplicate signals after restart
    global published_contracts
    published_contracts = load_published_contracts()
    if published_contracts:
        log.info("Loaded %d previously published contracts from disk", len(published_contracts))
    
    cycle = 0
    market_close_sent = False
    last_processed_ts = 0  # Track latest tick timestamp to avoid reprocessing
    
    while True:
        # Loop every 1 second
        time.sleep(1.0)
        
        # ── GLOBAL KILL SWITCH CHECK ──
        if Path("reports/panic.flag").exists():
            log.error("🚨 PANIC FLAG DETECTED! 🚨 Shutting down runner immediately.")
            send_telegram_message("🔴 *SYSTEM KILLED* via Panic Switch.")
            break
            
        # ── DAILY MAX LOSS CIRCUIT BREAKER (TRUE LEDGER) ──
        try:
            resp = httpx.get("http://localhost:4000/api/ledger", timeout=2.0)
            if resp.status_code == 200:
                ledger = resp.json()
                trades = ledger.get("trades", [])
                
                real_daily_pnl = 0.0
                open_trades = []
                now_date_str = datetime.now().strftime("%Y-%m-%d")
                
                for t in trades:
                    if t.get("status") == "CLOSED":
                        closed_at = t.get("exitTimestamp") or t.get("timestamp", "")
                        if "T" in str(closed_at):
                            closed_at = closed_at.replace("T", " ").split(".")[0]
                        if closed_at and closed_at.startswith(now_date_str):
                            real_daily_pnl += float(t.get("netPnl") or 0.0)
                    elif t.get("status") == "OPEN":
                        open_trades.append(t)
                        
                current_max_loss = get_dynamic_max_loss()
                if real_daily_pnl <= current_max_loss:
                    log.error("🛑 TRUE DAILY MAX LOSS BREACHED! PnL: ₹%.2f <= ₹%.2f.", real_daily_pnl, current_max_loss)
                    
                    if open_trades:
                        log.error("🔪 Killing %d OPEN trades forcefully due to Circuit Breaker...", len(open_trades))
                        for ot in open_trades:
                            try:
                                close_payload = {
                                    "action": "CLOSE",
                                    "tradeId": ot.get("id"),
                                    "exitPrice": ot.get("currentLtp") or ot.get("entryPrice")
                                }
                                httpx.post("http://localhost:4000/api/ledger/trade", json=close_payload, timeout=5.0)
                                log.info("Force Killed trade %s", ot.get("contractSymbol"))
                            except Exception as e:
                                log.error("Failed to kill trade %s: %s", ot.get("id"), e)
                                
                    send_telegram_message(f"🛑 *SYSTEM KILLED* via Daily Max Loss Circuit Breaker.\nDaily PnL: ₹{real_daily_pnl:.2f}\nOpen Trades Force Closed: {len(open_trades)}")
                    break
        except Exception as e:
            log.warning("Failed to fetch ledger for circuit breaker: %s", e)
            
        # Local fallback just in case backend is unreachable
        closed_trades = [s for s in all_signals if s.get("status") == "CLOSED"]
        daily_pnl = sum(s.get("pnl", 0) or 0 for s in closed_trades)
        current_max_loss = get_dynamic_max_loss()
        if daily_pnl <= current_max_loss:
            log.error("🛑 LOCAL DAILY MAX LOSS BREACHED! PnL: ₹%.2f. Shutting down runner immediately.", daily_pnl)
            send_telegram_message(f"🛑 *SYSTEM KILLED* via Local Circuit Breaker.\nDaily PnL: ₹{daily_pnl:.2f}")
            break
        
        # Liveness heartbeat for Node.js watchdog
        Path("reports").mkdir(exist_ok=True)
        with open("reports/heartbeat.txt", "w") as f:
            f.write(str(time.time()))
        
        # ── Intraday Macro Refresh (every 30 min) ────────────────
        if time.time() - macro_last_refresh >= MACRO_REFRESH_INTERVAL:
            try:
                from market.macro_sentiment import fetch_macro_data, invalidate_cache
                invalidate_cache()
                macro_cached_data = fetch_macro_data()
                macro_last_refresh = time.time()
                
                if macro_cached_data.get('risk_level') in ('HIGH', 'ELEVATED'):
                    macro_msg = format_macro_telegram_alert(macro_cached_data)
                    send_telegram_message(macro_msg)
                    log.info("MACRO REFRESH: %s (%.3f)", 
                            macro_cached_data['risk_level'], macro_cached_data['macro_risk_score'])
            except Exception as e:
                log.debug("Macro refresh failed: %s", e)
            
        # Check F&O market close (15:40 IST — derivatives extended session ends)
        now = datetime.now()
        if not args.ignore_market_hours and now.hour >= 15 and now.minute >= 40 and not market_close_sent:
            total_published = len(all_signals)
            winners = [s for s in all_signals if s.get("pnl_pct", 0) > 0]
            losers = [s for s in all_signals if s.get("pnl_pct", 0) < 0]
            send_telegram_message(
                "🔴 *MARKET CLOSED*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 Date: {DATE_STR}\n"
                f"📊 Total Signals: {total_published}\n"
                f"✅ Winners: {len(winners)}\n"
                f"❌ Losers: {len(losers)}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "Scanner stopped. See you tomorrow! 👋"
            )
            market_close_sent = True
            log.info("Market closed. Exiting.")
            break
            
        # Daily Max Trade Cap
        trades_today = check_daily_trade_limit()
        if trades_today >= 999:
            log.info(f"Daily trade limit reached ({trades_today}/999). Scanner deactivated for the day.")
            time.sleep(60)
            continue
            
        # Get UDP stream dataframe
        df_raw = get_udp_dataframe()
        if df_raw is None or df_raw.is_empty() or "timestamp" not in df_raw.columns:
            continue
        
        # Update module-level reference so lookup_contract_iv can access live ticks
        global _live_df_raw
        _live_df_raw = df_raw
            
        latest_udp_ts = df_raw["timestamp"].max()
        if latest_udp_ts <= last_processed_ts:
            # No new data arrived yet, just wait for next loop iteration
            continue
            
        last_processed_ts = latest_udp_ts
            
        cycle += 1
        if cycle % 10 == 0:
            log.info("--- Cycle %d (Buffer: %d ticks) ---", cycle, df_raw.height)
            
        # Run pipeline
        t_cycle_start = time.time()
        df_conf, elapsed, regime = run_pipeline(df_raw)
        
        # Flush latency concept is replaced by cycle evaluation latency
        flush_to_signal = round(time.time() - t_cycle_start, 3)
        flush_latencies.append(flush_to_signal)
        
        log.info("Pipeline completed in %.2fs (flush-to-signal: %.2fs)", elapsed, flush_to_signal)
        
        if df_conf.is_empty() or "confidence" not in df_conf.columns:
            log.info("No candidates this cycle.")
            # Still run lifecycle checks
            if all_signals:
                update_signal_lifecycle(df_raw, df_conf)
                rewrite_live_csv()
                print_status_dashboard()
            continue
        
        # Telegram Bot Command Intercepts
        is_paused = Path("config/pause.flag").exists()
        blocked_symbols = get_blocked_symbols()
        
        if is_paused:
            log.warning("⏸️ ENGINE PAUSED VIA TELEGRAM. Skipping new entries.")
            df_pub = pl.DataFrame()
        else:
            # Filter publishable
            df_pub = df_conf.filter(
                (pl.col("confidence").is_not_nan()) & 
                (pl.col("confidence").is_not_null()) & 
                (pl.col("confidence") >= PUBLISH_THRESHOLD) &
                (~pl.col("underlying").is_in(blocked_symbols))
            )
        
        log.info("Cycle Time: %s | Candidates: %d total, %d above threshold", datetime.now().strftime("%H:%M:%S"), df_conf.height, df_pub.height if not df_pub.is_empty() else 0)
        
        if df_pub.is_empty():
            peak = round(float(df_conf["confidence"].max()), 4)
            log.info("Peak confidence: %s (below threshold)", peak)
            # Still run lifecycle checks
            if all_signals:
                update_signal_lifecycle(df_raw, df_conf)
                rewrite_live_csv()
                print_status_dashboard()
            continue
        
        # Run lifecycle updates on existing signals
        if all_signals:
            changes = update_signal_lifecycle(df_raw, df_conf)
        
        # Deduplicate & Select Best via Execution Optimizer
        now = datetime.now()
        gen_dt = now
        new_signals = 0
        
        candidates_by_group = {}
        total_candidates = df_pub.height
        
        df_latest = None
        if not df_raw.is_empty():
            latest_ts_val = df_raw["timestamp"].max()
            df_latest = df_raw.filter(pl.col("timestamp") == latest_ts_val)
        
        # 1. Gather executable candidates
        current_rank = 1
        for row in df_pub.sort("confidence", descending=True).iter_rows(named=True):
            # Calculate regime for the trade
            vol_regime = row.get("volatility_regime", 0.5)
            momentum = abs(row.get("momentum_5", 0) or 0)
            reg_conf = row.get("regime_confidence", 40)
            underlying = row.get("underlying", "")
            current_regime = current_regimes.get(underlying, "CHOPPY_MEAN_REVERSION")
            is_trending = (reg_conf > 60 or momentum > 0.012) and current_regime == "TRENDING_MOMENTUM"
            row["is_trending"] = is_trending
            
            # Default action if not present
            if "action" not in row or not row["action"]:
                row["action"] = "BUY" if is_trending else "SELL"
                
            contract_key = (
                row.get("underlying", ""),
                str(row.get("expiry", "")),
                row.get("strike", 0),
                row.get("option_type", ""),
            )
            
            if contract_key in published_contracts:
                continue
                
            executable, reason = is_executable(row)
            
            # Log every generated idea, including rejected ones, for user review (with 60s deduplication)
            idea_key = (
                row.get("underlying", ""),
                row.get("strike", 0),
                row.get("option_type", ""),
                row.get("action", "BUY"),
                reason if not executable else "APPROVED"
            )
            now_dt_log = datetime.now()
            last_logged = _last_idea_logged_time.get(idea_key)
            if last_logged is None or (now_dt_log - last_logged).total_seconds() >= 60:
                _last_idea_logged_time[idea_key] = now_dt_log
                ideas_log = Path("reports/all_generated_ideas.jsonl")
                ideas_log.parent.mkdir(parents=True, exist_ok=True)
                with open(ideas_log, "a") as f:
                    log_data = {
                        "timestamp": now_dt_log.strftime("%Y-%m-%d %H:%M:%S"),
                        "underlying": row.get("underlying", ""),
                        "strike": row.get("strike", 0),
                        "option_type": row.get("option_type", ""),
                        "action": row.get("action", "BUY"),
                        "confidence": round(row.get("confidence", 0), 4),
                        "is_executable": executable,
                        "rejection_reason": reason if not executable else "APPROVED"
                    }
                    f.write(json.dumps(log_data) + "\n")

            if not executable:
                log.debug(
                    "REJECTED: %s %s %s | conf=%.4f reason=%s",
                    row.get("underlying", ""), row.get("strike", 0),
                    row.get("option_type", ""), row.get("confidence", 0), reason
                )
                continue
            
            # Group by underlying and direction (e.g. NIFTY CE)
            group_key = (row.get("underlying", ""), row.get("option_type", ""))
            if group_key not in candidates_by_group:
                candidates_by_group[group_key] = []
            
            # Keep top 3 per group
            if len(candidates_by_group[group_key]) < 3:
                row_copy = dict(row)
                row_copy["_signal_rank"] = current_rank
                row_copy["_total_candidates"] = total_candidates
                candidates_by_group[group_key].append(row_copy)
            
            current_rank += 1
            
        # 2. Execution Optimizer
        final_ideas = []
        for group_key, candidates in candidates_by_group.items():
            best_idea = None
            best_exec_score = -999.0
            
            candidate_list_telemetry = {}
            for i, cand in enumerate(candidates):
                contract_iv = lookup_contract_iv(cand.get("underlying", ""), cand.get("strike", 0), cand.get("option_type", ""))
                d = approximate_delta(cand.get("spot", 0), cand.get("strike", 0), cand.get("expiry", ""), cand.get("option_type", ""), iv=contract_iv)
                tp = fair_price(cand.get("spot", 0), cand.get("strike", 0), cand.get("expiry", ""), cand.get("option_type", ""), iv=contract_iv)
                gamma, vega, theta, vanna, vomma, charm, speed = calculate_greeks(cand.get("spot", 0), cand.get("strike", 0), cand.get("expiry", ""), cand.get("option_type", ""), iv=contract_iv)
                ltp = cand.get("ltp", 0) or 0
                candidate_list_telemetry[f"candidate_{i+1}"] = {
                    "strike": cand.get("strike", 0),
                    "confidence": round(cand.get("confidence", 0), 4),
                    "delta": round(d, 4),
                    "iv": round(contract_iv * 100, 2),  # store as percentage for readability
                    "fair_price": round(tp, 2),
                    "fair_value_gap": round(ltp - tp, 2),
                    "gamma": round(gamma, 4),
                    "vega": round(vega, 2),
                    "theta": round(theta, 2),
                    "vanna": round(vanna, 4),
                    "vomma": round(vomma, 4),
                    "charm": round(charm, 4),
                    "speed": round(speed, 6)
                }
            
            for idx, c in enumerate(candidates):
                idea = build_trade_idea(c, gen_dt, df_latest, df_raw=df_raw)
                if idea is None:
                    continue
                
                # Reuse Greeks from telemetry loop instead of recomputing
                telem_key = f"candidate_{idx+1}"
                telem = candidate_list_telemetry.get(telem_key, {})
                delta = telem.get("delta", 0.5)
                contract_iv = telem.get("iv", 15.0) / 100.0  # stored as %, convert back
                tp = telem.get("fair_price", 0)
                gamma = telem.get("gamma", 0)
                vega = telem.get("vega", 0)
                theta = telem.get("theta", 0)
                vanna = telem.get("vanna", 0)
                vomma = telem.get("vomma", 0)
                charm = telem.get("charm", 0)
                speed = telem.get("speed", 0)
                delta_score = calculate_delta_score(delta)
                
                # SpreadScore (0.0 to 1.0 normalized) - lower spread = higher score
                bid = c.get("bid", 0) or 0
                ask = c.get("ask", 0) or 0
                mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else 1
                spread_pct = (ask - bid) / mid if mid > 0 else 1.0
                spread_score = max(0.0, min(1.0, 1.0 - (spread_pct / 0.05)))  # 0% spread = 1.0, 5%+ = 0.0
                
                # LiquidityScore (0.0 to 1.0 normalized) - higher volume = higher score
                vol = c.get("volume", 0) or 0
                liq_score = min(1.0, vol / 500000.0)  # 500k+ vol = 1.0
                
                # Normalized Execution Score (confidence dominates, execution breaks ties)
                exec_score = (
                    0.80 * idea["effective_confidence"] +
                    0.10 * delta_score +
                    0.05 * spread_score +
                    0.05 * liq_score
                )
                
                idea["selected_delta"] = round(delta, 4)
                idea["selected_iv"] = round(contract_iv * 100, 2)  # percentage
                idea["fair_price"] = round(tp, 2)
                idea["fair_value_gap"] = round((c.get("ltp", 0) or 0) - tp, 2)
                idea["gamma"] = round(gamma, 4)
                idea["vega"] = round(vega, 2)
                idea["theta"] = round(theta, 2)
                idea["vanna"] = round(vanna, 4)
                idea["vomma"] = round(vomma, 4)
                idea["charm"] = round(charm, 4)
                idea["speed"] = round(speed, 6)
                idea["execution_score"] = round(exec_score, 4)
                idea["execution_score_components"] = {
                    "confidence": round(idea["effective_confidence"], 4),
                    "delta": round(delta_score, 4),
                    "spread": round(spread_score, 4),
                    "liquidity": round(liq_score, 4)
                }
                idea["execution_rank"] = idx + 1
                idea["signal_rank"] = c["_signal_rank"]
                idea["total_candidates"] = c["_total_candidates"]
                idea["candidate_list"] = candidate_list_telemetry
                
                # Track all scored candidates for selected_reason derivation
                idea["_exec_score"] = exec_score
                idea["_exec_components"] = {
                    "confidence": idea["effective_confidence"],
                    "delta": delta_score,
                    "spread": spread_score,
                    "liquidity": liq_score
                }
                
                if exec_score > best_exec_score:
                    best_exec_score = exec_score
                    best_idea = idea
            
            # Derive selected_reason: why did the winner beat others?
            if best_idea and len(candidates) > 1:
                reasons = ["highest_execution_score"]
                best_comp = best_idea["_exec_components"]
                
                for other_key in ["candidate_1", "candidate_2", "candidate_3"]:
                    other = candidate_list_telemetry.get(other_key, {})
                    if other.get("strike") == best_idea["strike"]:
                        continue
                    if other.get("delta") and abs(best_comp["delta"]) > abs(other.get("delta", 0)):
                        if "delta_preferred" not in reasons:
                            reasons.append("delta_preferred")
                    if best_comp["spread"] > 0.5:
                        if "better_spread" not in reasons:
                            reasons.append("better_spread")
                    if best_comp["liquidity"] > 0.5:
                        if "higher_liquidity" not in reasons:
                            reasons.append("higher_liquidity")
                    if best_comp["confidence"] >= other.get("confidence", 0):
                        if "higher_confidence" not in reasons:
                            reasons.append("higher_confidence")
                
                best_idea["selected_reason"] = reasons
            elif best_idea:
                best_idea["selected_reason"] = ["only_candidate"]
            
            if best_idea:
                final_ideas.append(best_idea)

        # 3. Global Priority Ranking & Publishing
        final_ideas.sort(key=lambda x: x.get("execution_score", 0), reverse=True)
        
        for best_idea in final_ideas:
                # DEBUG: Trace exactly what's happening in the publish gates
                log.info("PUBLISH_GATE_DEBUG: %s %s %s | entry=%.2f | fvg=%.2f | has_features=%s | exec_score=%.4f",
                         best_idea.get("underlying", ""), best_idea.get("strike", 0), best_idea.get("option_type", ""),
                         best_idea.get("entry", 0), best_idea.get("fair_value_gap", -999),
                         bool(best_idea.get("_features", {})), best_idea.get("execution_score", 0))
                
                # ── STRICT PUBLISHING RATE LIMITER ──
                # This prevents the engine from generating multiple candidates in the SAME cycle
                # and publishing them all simultaneously.
                now_dt_pub = datetime.now()
                recent_published = [
                    s for s in all_signals 
                    if s.get("generated_at") and 
                    (now_dt_pub - datetime.strptime(s["generated_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() < 5 * 60
                ]
                
                skip_publish = False
                reject_reason = ""
                if len(recent_published) >= 2:
                    reject_reason = "Max 2 trades per 5 min reached"
                    log.warning("BLOCKED PUBLISH: %s", reject_reason)
                    skip_publish = True
                elif recent_published:
                    last_signal = max(recent_published, key=lambda s: s["generated_at"])
                    last_time = datetime.strptime(last_signal["generated_at"], "%Y-%m-%d %H:%M:%S")
                    elapsed = (now_dt_pub - last_time).total_seconds()
                    if elapsed < 3 * 60:
                        reject_reason = f"3-minute cooldown active. {int(180 - elapsed)}s remaining."
                        log.warning("BLOCKED PUBLISH: %s", reject_reason)
                        skip_publish = True
                
                # Check for opposite direction in the same underlying
                if not skip_publish:
                    for s in recent_published:
                        if s.get("underlying") == best_idea["underlying"] and s.get("option_type") != best_idea["option_type"]:
                            reject_reason = f"Opposite direction trade already taken on {best_idea['underlying']} recently."
                            log.warning("BLOCKED PUBLISH: %s", reject_reason)
                            skip_publish = True
                            break
                            
                # STRICT METRICS GATE: Prevent blind execution
                if not skip_publish:
                    features = best_idea.get("_features", {})
                    missing_metrics = []
                    idea_strategy = best_idea.get("strategy", "Momentum Breakout")
                    if idea_strategy == "Mean Reversion":
                        critical_metrics = [
                            "vwap_deviation", "s_vwap_fade", "s_exhaustion"
                        ]
                    else:
                        critical_metrics = [
                            "rsi_14", "vwap_deviation", "trend_regime", "vwoim",
                            "volume_burst", "s_oi_flow", "s_vwap", "momentum_5"
                        ]
                    for critical_metric in critical_metrics:
                        if features.get(critical_metric) is None:
                            missing_metrics.append(critical_metric)
                    
                    if missing_metrics:
                        reject_reason = f"Blind trade detected. Missing core metrics: {missing_metrics}"
                        log.warning("BLOCKED PUBLISH: %s", reject_reason)
                        skip_publish = True
                            
                # FAIR VALUE GAP GATE: Block execution if option is overvalued (FVG > 0)
                if not skip_publish:
                    fvg = best_idea.get("fair_value_gap")
                    idea_strategy = best_idea.get("strategy", "Momentum Breakout")
                    if fvg is not None and fvg > 0 and idea_strategy != "Mean Reversion":
                        reject_reason = f"Option is overpriced (Fair Value Gap = {fvg:.2f} > 0)."
                        log.warning("BLOCKED PUBLISH: %s", reject_reason)
                        skip_publish = True
                            
                if skip_publish:
                    with open("reports/publish_rejections.log", "a") as f:
                        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {best_idea['underlying']} {best_idea['strike']} {best_idea['option_type']} - {reject_reason}\n")
                    continue
                
                publish_signal(best_idea)
                print_trade_banner(best_idea)
                
                contract_key = (
                    best_idea["underlying"],
                    str(best_idea["expiry"]),
                    best_idea["strike"],
                    best_idea["option_type"],
                )
                published_contracts.add(contract_key)
                save_published_contracts()
                all_signals.append(best_idea)
                new_signals += 1
                
                # SDT: Track direction for Same-Direction Throttle
                _track_direction(best_idea["option_type"])
                
                log.info(
                    "PUBLISHED: %s %s %s %s | conf=%.4f exec_score=%.4f entry=%.2f stop=%.2f t1=%.2f",
                    best_idea["underlying"], best_idea["expiry"], best_idea["strike"],
                    best_idea["option_type"], best_idea["effective_confidence"],
                    best_idea["execution_score"], best_idea["entry"],
                    best_idea["stop"], best_idea["target1"]
                )
        
        log.info("New signals: %d | Total published: %d", new_signals, len(published_contracts))
        
        # Rewrite live CSV to reflect current statuses
        rewrite_live_csv()
        
        # Dashboard
        print_status_dashboard()
        
        # 3. Liveness Watchdog (heartbeat.txt)
        # Node.js polls this file to ensure the Python engine hasn't silently crashed
        heartbeat_file = Path("reports/heartbeat.txt")
        heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        with open(heartbeat_file, "w") as f:
            f.write(str(time.time()))
        
        # Latency stats
        if flush_latencies:
            sorted_lat = sorted(flush_latencies)
            median_lat = sorted_lat[len(sorted_lat) // 2]
            log.info("Flush-to-signal latency: median=%.2fs, latest=%.2fs", median_lat, flush_to_signal)
            
            if median_lat < 60:
                log.info("STATUS: REALTIME_READY (median < 60s)")
            else:
                log.info("STATUS: NEEDS_OPTIMIZATION (median >= 60s)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        
        # Final summary
        if flush_latencies:
            sorted_lat = sorted(flush_latencies)
            median_lat = sorted_lat[len(sorted_lat) // 2]
        else:
            median_lat = 0
        
        # Count statuses
        now = datetime.now()
        live_count = 0
        expired_count = 0
        for sig in all_signals:
            win_end = sig.get("_win_end_dt")
            if win_end and now > win_end:
                expired_count += 1
            else:
                live_count += 1
        
        # Median signal life
        signal_lives = []
        for sig in all_signals:
            win_end = sig.get("_win_end_dt")
            gen_str = sig.get("generated_at", "")
            if win_end and gen_str:
                try:
                    gen_dt = datetime.strptime(gen_str, "%Y-%m-%d %H:%M:%S")
                    life = (win_end - gen_dt).total_seconds()
                    signal_lives.append(life)
                except:
                    pass
        median_life = sorted(signal_lives)[len(signal_lives)//2] if signal_lives else 0
        
        has_timing = all("entry_window_start" in s for s in all_signals) if all_signals else True
        
        if has_timing and len(all_signals) > 0:
            decision = "TIMED_SIGNALS_READY"
        elif median_lat < 60:
            decision = "REALTIME_READY"
        else:
            decision = "NEEDS_OPTIMIZATION"
        
        print()
        print("OUTPUT:")
        print("published: " + str(len(all_signals)))
        print("live: " + str(live_count))
        print("expired: " + str(expired_count))
        print("median_signal_life: " + str(round(median_life)) + "s")
        print("decision: " + decision)
        print("STOP")
