"""
NSE India Market Data Client.

Uses curl_cffi to bypass Akamai TLS fingerprint detection.
Endpoints discovered from live NSE website (24-Jun-2026).

Data Sources:
1. Option Chain v3 (PCR, Max Pain, IV Skew, OI walls)
2. OI Spurts - contracts (sudden OI changes in specific contracts)
3. OI Spurts - underlyings (OI changes per underlying)
4. Most Active Contracts (liquidity & institutional targets)
5. Equity Derivatives Watch (top 20 active contracts)
"""
import time
from loguru import logger
from typing import Dict, Any, Optional
from curl_cffi import requests as curl_requests


class NSEClient:
    BASE_URL = "https://www.nseindia.com"
    
    # Correct endpoints as of Jun 2026 (discovered from live NSE website)
    ENDPOINTS = {
        # Option Chain v3 — replaces old /api/option-chain-indices
        "option_chain_v3": "/api/option-chain-v3",
        # Contract info for option chain page
        "option_chain_info": "/api/option-chain-contract-info",
        # OI Spurts — contracts level (individual strike OI changes)
        "oi_spurts_contracts": "/api/live-analysis-oi-spurts-contracts",
        # OI Spurts — underlyings level (aggregate OI per symbol)
        "oi_spurts_underlyings": "/api/live-analysis-oi-spurts-underlyings",
        # Most Active — replaces old /api/live-analysis-most-active-contracts
        "most_active": "/api/snapshot-derivatives-equity",
        # Equity Derivatives Watch — top 20 active contracts
        "derivatives_watch": "/api/liveEquity-derivatives",
    }
    
    REFERERS = {
        "option_chain_v3": "/option-chain",
        "option_chain_info": "/option-chain",
        "oi_spurts_contracts": "/market-data/oi-spurts",
        "oi_spurts_underlyings": "/market-data/oi-spurts",
        "most_active": "/market-data/most-active-contracts",
        "derivatives_watch": "/market-data/equity-derivatives-watch",
    }
    
    def __init__(self, ttl_sec: int = 30):
        self.ttl_sec = ttl_sec
        self.cache: Dict[str, Any] = {}
        self.last_fetch_time: Dict[str, float] = {}
        self._session: Optional[curl_requests.Session] = None
        self._cookie_time: float = 0
        self._cookie_max_age: float = 90  # refresh cookies every 90s

    def _get_session(self) -> curl_requests.Session:
        """Get or create the curl_cffi session with Chrome TLS fingerprint."""
        if self._session is None:
            self._session = curl_requests.Session(impersonate="chrome")
        return self._session

    def _refresh_cookies(self, force: bool = False) -> bool:
        """Hit NSE homepage to get valid session cookies."""
        now = time.time()
        if not force and (now - self._cookie_time) < self._cookie_max_age:
            return True
        
        session = self._get_session()
        try:
            resp = session.get(self.BASE_URL, timeout=10)
            if resp.status_code == 200:
                self._cookie_time = now
                logger.debug("NSE cookies refreshed OK (curl_cffi)")
                return True
            else:
                logger.warning(f"NSE homepage returned {resp.status_code}")
                return False
        except Exception as e:
            logger.warning(f"NSE cookie refresh failed: {e}")
            return False

    def _fetch(self, endpoint_key: str, params: str = "") -> Optional[Dict]:
        """Core synchronous fetch with cookie management and caching."""
        cache_key = f"{endpoint_key}_{params}" if params else endpoint_key
        now = time.time()
        
        # Check cache
        if cache_key in self.cache:
            if (now - self.last_fetch_time.get(cache_key, 0)) < self.ttl_sec:
                return self.cache[cache_key]
        
        self._refresh_cookies()
        session = self._get_session()
        
        url = f"{self.BASE_URL}{self.ENDPOINTS[endpoint_key]}"
        if params:
            url += f"?{params}"
        
        referer = f"{self.BASE_URL}{self.REFERERS.get(endpoint_key, '/')}"
        
        for attempt in range(2):
            try:
                resp = session.get(
                    url,
                    headers={"Referer": referer},
                    timeout=10
                )
                
                if resp.status_code in (401, 403, 404):
                    if attempt == 0:
                        logger.debug(f"NSE {resp.status_code} for {cache_key}, refreshing cookies...")
                        self._refresh_cookies(force=True)
                        continue
                    else:
                        logger.warning(f"NSE {resp.status_code} for {cache_key} after retry")
                        break
                
                resp.raise_for_status()
                data = resp.json()
                
                self.cache[cache_key] = data
                self.last_fetch_time[cache_key] = time.time()
                logger.debug(f"NSE {cache_key}: fetched OK")
                return data
                
            except Exception as e:
                if attempt == 0:
                    logger.debug(f"NSE fetch {cache_key} error: {e}, retrying...")
                    self._refresh_cookies(force=True)
                    continue
                logger.warning(f"NSE fetch {cache_key} failed: {e}")
                break
        
        # Return stale cache if available
        if cache_key in self.cache:
            logger.info(f"Returning stale NSE cache for {cache_key}")
            return self.cache[cache_key]
        return None

    # ── Public API (sync internally, async-compatible interface) ──

    async def get_option_chain(self, symbol: str, expiry: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch option chain v3 for NIFTY/BANKNIFTY.
        
        The v3 endpoint requires type, symbol, and optionally expiry.
        If no expiry is given, tries without expiry first (NSE may auto-select nearest).
        """
        # First try: get contract info to find current expiry
        if not expiry:
            info = self._fetch("option_chain_info", f"symbol={symbol}")
            if info:
                expiries = info.get("expiryDates", [])
                if expiries:
                    expiry = expiries[0]  # nearest expiry
                    logger.debug(f"NSE {symbol}: auto-selected expiry {expiry}")
        
        # Build params for v3 endpoint
        asset_type = "Indices" if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"] else "Equity"
        params = f"type={asset_type}&symbol={symbol}"
        if expiry:
            params += f"&expiry={expiry}"
        
        data = self._fetch("option_chain_v3", params)
        
        if data:
            records = data.get("records", data.get("filtered", {}))
            data_list = records.get("data", [])
            if not data_list:
                # Try with just records key directly
                if "data" in data and isinstance(data["data"], list):
                    return data
                logger.warning(f"Empty option chain for {symbol}")
                return None
        return data

    async def get_oi_spurts_contracts(self) -> Optional[Dict[str, Any]]:
        """
        Fetch OI Spurts at contract level — individual strikes with sudden OI changes.
        Shows WHERE smart money is flowing into specific options.
        """
        return self._fetch("oi_spurts_contracts")

    async def get_oi_spurts_underlyings(self) -> Optional[Dict[str, Any]]:
        """
        Fetch OI Spurts at underlying level — aggregate OI changes per symbol.
        Shows WHICH underlying is seeing institutional activity.
        """
        return self._fetch("oi_spurts_underlyings")

    async def get_most_active_contracts(self) -> Optional[Dict[str, Any]]:
        """
        Fetch most active derivative contracts (equity).
        Uses snapshot-derivatives-equity endpoint.
        """
        return self._fetch("most_active", "index=contracts&limit=20")

    async def get_derivatives_watch(self) -> Optional[Dict[str, Any]]:
        """
        Fetch equity derivatives watch — top 20 active contracts.
        Replaces old quote-derivative endpoint.
        """
        return self._fetch("derivatives_watch", "index=top20_contracts")

    async def close(self):
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None
