import os
import gzip
import json
import time
import httpx
from datetime import datetime
from pathlib import Path
from loguru import logger
from typing import Dict, Optional

class InstrumentResolver:
    URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    CACHE_FILE = Path("runtime/NSE.json.gz")
    MAX_AGE_SEC = 86400  # 1 day

    def __init__(self):
        self.lookup_table: Dict[str, str] = {}
        self.reverse_lookup_table: Dict[str, dict] = {}
        self.expiries_by_underlying: Dict[str, set] = {}
        self.is_loaded = False

    async def ensure_loaded(self):
        if self.is_loaded:
            return

        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        needs_download = True
        if self.CACHE_FILE.exists():
            age = time.time() - self.CACHE_FILE.stat().st_mtime
            if age < self.MAX_AGE_SEC:
                needs_download = False
                
        if needs_download:
            logger.info("Downloading Upstox NSE instruments...")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.URL, headers={'User-Agent': 'Mozilla/5.0'})
                    response.raise_for_status()
                    with open(self.CACHE_FILE, "wb") as f:
                        f.write(response.content)
                logger.info("Download complete.")
            except Exception as e:
                logger.error(f"Failed to download instruments: {e}")
                if not self.CACHE_FILE.exists():
                    raise RuntimeError("No instrument cache available.") from e
        
        self._build_lookup_table()
        self.is_loaded = True

    def _build_lookup_table(self):
        logger.info("Building instrument lookup table...")
        try:
            with gzip.open(self.CACHE_FILE, "rt", encoding="utf-8") as f:
                data = json.load(f)
                
            for item in data:
                if item.get("segment") == "NSE_FO" and item.get("instrument_type") in ("CE", "PE"):
                    underlying = item.get("underlying_symbol", "")
                    strike = float(item.get("strike_price", 0))
                    opt_type = item.get("instrument_type", "")
                    expiry_ms = item.get("expiry", 0)
                    
                    if not (underlying and strike and opt_type and expiry_ms):
                        continue
                        
                    # Convert ms to date string YYYY-MM-DD
                    expiry_date = datetime.fromtimestamp(expiry_ms / 1000.0).strftime("%Y-%m-%d")
                    
                    key = f"{underlying}_{expiry_date}_{strike}_{opt_type}"
                    instrument_key = item.get("instrument_key", "")
                    self.lookup_table[key] = instrument_key
                    
                    self.reverse_lookup_table[instrument_key] = {
                        "underlying": underlying,
                        "expiry": expiry_date,
                        "strike": strike,
                        "option_type": opt_type
                    }
                    
                    if underlying not in self.expiries_by_underlying:
                        self.expiries_by_underlying[underlying] = set()
                    self.expiries_by_underlying[underlying].add(expiry_date)
                    
            logger.info(f"Loaded {len(self.lookup_table)} F&O instruments.")
        except Exception as e:
            logger.error(f"Failed to parse instruments: {e}")
            raise

    def resolve(self, underlying: str, nse_expiry: str, strike: float, opt_type: str) -> Optional[str]:
        """
        Resolve option to instrument_key.
        nse_expiry should be in 'dd-MMM-yyyy' format (e.g. '26-Jun-2024') or V3 'DD-MM-YYYY'
        """
        try:
            # Convert NSE expiry. Try new V3 format (DD-MM-YYYY) first
            try:
                dt = datetime.strptime(nse_expiry, "%d-%m-%Y")
            except ValueError:
                # Fallback to old format (DD-MMM-YYYY)
                dt = datetime.strptime(nse_expiry, "%d-%b-%Y")
            
            # Reject synthetic dates
            if dt.year < 2023 or dt.year > 2050:
                logger.warning(f"Rejecting synthetic date: {nse_expiry}")
                return None
                
            formatted_expiry = dt.strftime("%Y-%m-%d")
            
            key = f"{underlying}_{formatted_expiry}_{float(strike)}_{opt_type}"
            if key in self.lookup_table:
                return self.lookup_table[key]
                
            # Fallback to nearest expiry
            if underlying in self.expiries_by_underlying:
                available = sorted([datetime.strptime(e, "%Y-%m-%d") for e in self.expiries_by_underlying[underlying]])
                future = [e for e in available if e >= dt]
                if future:
                    nearest = future[0]
                    nearest_str = nearest.strftime("%Y-%m-%d")
                    fallback_key = f"{underlying}_{nearest_str}_{float(strike)}_{opt_type}"
                    if fallback_key in self.lookup_table:
                        logger.info(f"Fallback to nearest expiry: {formatted_expiry} -> {nearest_str}")
                        return self.lookup_table[fallback_key]
                        
            return None
        except Exception as e:
            logger.warning(f"Failed to resolve {underlying} {strike} {opt_type} {nse_expiry}: {e}")
            return None

    def resolve_from_key(self, instrument_key: str) -> Optional[dict]:
        """
        Reverse lookup: instrument_key -> dict(underlying, expiry, strike, option_type)
        """
        return self.reverse_lookup_table.get(instrument_key)
