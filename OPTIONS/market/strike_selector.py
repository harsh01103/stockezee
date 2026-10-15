import time
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from typing import List, Dict, Any, Tuple

from market.nse_client import NSEClient

class StrikeSelector:
    def __init__(self, nse_client: NSEClient):
        self.nse_client = nse_client
        self.universe: Dict[str, List[Dict[str, Any]]] = {
            "NIFTY": [],
            "BANKNIFTY": []
        }
        self.last_update = 0.0

    async def _get_atm_and_strikes(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Parses the NSE option chain, finds the nearest weekly expiry,
        determines ATM, and returns ATM ±7 strikes data.
        """
        data = await self.nse_client.get_option_chain(symbol)
        if not data or "records" not in data or "data" not in data["records"]:
            if self.universe[symbol]:
                return self.universe[symbol] # return stale if fail
            else:
                logger.warning(f"NSE cache empty. Generating fallback universe for {symbol}.")
                return self.generate_fallback_universe(symbol)

        records = data["records"]
        underlying_val = records.get("underlyingValue")
        if not underlying_val:
            if self.universe[symbol]:
                return self.universe[symbol]
            else:
                return self.generate_fallback_universe(symbol)

        # Find nearest expiry
        expiry_dates = records.get("expiryDates", [])
        if not expiry_dates:
            return self.universe[symbol]
            
        current_expiry = expiry_dates[0]
        
        # Filter for current expiry
        options_data = [d for d in records["data"] if d.get("expiryDate", current_expiry) == current_expiry]
        if not options_data:
            return self.universe[symbol]
            
        # Find ATM strike
        strikes = sorted(list(set([d["strikePrice"] for d in options_data])))
        atm_strike = min(strikes, key=lambda x: abs(x - underlying_val))
        
        # Find ATM index
        try:
            atm_index = strikes.index(atm_strike)
        except ValueError:
            return self.universe[symbol]
            
        # ATM +/- 7 strikes
        start_idx = max(0, atm_index - 7)
        end_idx = min(len(strikes), atm_index + 8)
        selected_strikes = set(strikes[start_idx:end_idx])
        
        selected_data = [d for d in options_data if d["strikePrice"] in selected_strikes]
        return selected_data

    def generate_fallback_universe(self, symbol: str, spot: float = None) -> List[Dict[str, Any]]:
        """Generates a static ATM ±7 universe if NSE API is completely down on cold start."""
        if spot is None:
            spot = 23800.0 if symbol == "NIFTY" else 58100.0
            
        step = 50.0 if symbol == "NIFTY" else 100.0
        
        # Round spot to nearest step
        atm_strike = round(spot / step) * step
        
        # Find next Thursday
        today = datetime.now()
        days_ahead = 3 - today.weekday()
        if days_ahead < 0: # Target day already happened this week
            days_ahead += 7
        next_thursday = today + timedelta(days=days_ahead)
        expiry_str = next_thursday.strftime("%d-%b-%Y")
        
        strikes = [atm_strike + (i * step) for i in range(-7, 8)]
        
        fallback_data = []
        for strike in strikes:
            fallback_data.append({
                "strikePrice": strike,
                "expiryDate": expiry_str,
                "underlying": symbol,
                "optionType": "CE",
                "source": "fallback"
            })
            fallback_data.append({
                "strikePrice": strike,
                "expiryDate": expiry_str,
                "underlying": symbol,
                "optionType": "PE",
                "source": "fallback"
            })
            
        if not fallback_data:
            raise ValueError(f"Failed to generate fallback universe for {symbol}")
            
        return fallback_data

    async def update_universe(self):
        """Update the strike universe for both NIFTY and BANKNIFTY."""
        now = time.time()
        # Refresh every 60 seconds
        if now - self.last_update < 60:
            return
            
        logger.info("Updating dynamic strike universe...")
        
        nifty_strikes = await self._get_atm_and_strikes("NIFTY")
        banknifty_strikes = await self._get_atm_and_strikes("BANKNIFTY")
        
        self.universe["NIFTY"] = nifty_strikes
        self.universe["BANKNIFTY"] = banknifty_strikes
        self.last_update = time.time()
        
        logger.debug(f"Universe updated: {len(nifty_strikes)} NIFTY strikes, {len(banknifty_strikes)} BANKNIFTY strikes")

    def get_selected_strikes(self, symbol: str) -> List[Dict[str, Any]]:
        return self.universe.get(symbol, [])
