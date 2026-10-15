import asyncio
import httpx
from loguru import logger
from typing import Dict, Any, Optional

class UpstoxExecutor:
    """
    Direct asynchronous execution engine to hit Upstox Order API.
    Bypasses Node.js webhook layer for minimum latency.
    """
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        self.auth_manager = auth_manager
        self.base_url = "https://api.upstox.com/v2/order/place"
        self.details_url = "https://api.upstox.com/v2/order/details"

    async def _post_order(self, payload: Dict[str, Any], attempt: int = 1) -> Optional[Dict]:
        token = self.auth_manager.get_access_token()
        if not token:
            logger.error("UpstoxExecutor: Missing access token.")
            return None

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=5.0
                )
                
                if response.status_code == 401 and attempt == 1:
                    logger.warning("UpstoxExecutor: 401 Unauthorized. Refreshing token...")
                    await self.auth_manager.silent_refresh()
                    return await self._post_order(payload, attempt=2)
                    
                response.raise_for_status()
                data = response.json()
                logger.info(f"Upstox API Order Success: {data}")
                return data
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Upstox API HTTP Error: {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Upstox API Request Failed: {e}")
                return None

    async def _get_filled_quantity(self, order_id: str) -> Optional[int]:
        """Micro-polling loop to get terminal order status using order/details API."""
        token = self.auth_manager.get_access_token()
        if not token:
            return None
            
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient() as client:
            for attempt in range(3):
                try:
                    resp = await client.get(
                        f"{self.details_url}?order_id={order_id}",
                        headers=headers,
                        timeout=5.0
                    )
                    resp.raise_for_status()
                    data = resp.json().get("data", [])
                    
                    if data:
                        # order/details returns an array or single dict, usually array of length 1
                        latest_state = data[0] if isinstance(data, list) else data
                        status = latest_state.get("status", "").lower()
                        filled_qty = int(latest_state.get("filled_quantity", 0))
                        
                        if status in ["complete", "cancelled", "rejected"]:
                            return filled_qty
                            
                except Exception as e:
                    logger.warning(f"Failed to poll order status for {order_id}: {e}")
                
                # Sleep before retry
                await asyncio.sleep(0.3)
                
        return None

    async def execute_trade(self, instrument_token: str, quantity: int, entry_price: float, stop_price: float, transaction_type: str = "BUY", fair_value: Optional[float] = None):
        """
        Executes a dual-order sequence (Adjustment 2):
        1. Limit Entry Order (IOC - Immediate or Cancel) to bypass rate limits and absorb slippage.
        2. Intraday Stop-Loss Limit Order
        """
        logger.info(f"EXECUTOR THREAD: Launching sequence for {instrument_token} | {transaction_type} QTY {quantity} @ {entry_price}")
        
        # 1. Fair Value Slippage Check
        if fair_value is not None and fair_value > 0:
            if transaction_type == "BUY" and entry_price > fair_value * 1.005:
                logger.error(f"EXECUTOR ABORT: Entry {entry_price} exceeds Fair Value {fair_value} by > 0.5%. Slippage unacceptable.")
                return False
                
        # 2. Fire Entry Order
        entry_payload = {
            "quantity": quantity,
            "product": "I", # Intraday
            "validity": "IOC", # Changed to Immediate-Or-Cancel
            "price": entry_price,
            "tag": "alpha_engine",
            "instrument_token": instrument_token,
            "order_type": "LIMIT",
            "transaction_type": transaction_type,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False
        }
        
        entry_result = await self._post_order(entry_payload)
        
        if not entry_result or entry_result.get("status") != "success":
            logger.error(f"EXECUTOR ABORT: Entry order API call failed for {instrument_token}. Stop loss will not be placed.")
            return False
            
        order_id = entry_result.get("data", {}).get("order_id")
        if not order_id:
            logger.error("EXECUTOR ABORT: Missing order_id in success response.")
            return False
            
        logger.info(f"ENTRY PLACED for {instrument_token}. OrderID: {order_id}. Polling for fill...")
        
        # 1b. Poll for IOC Partial/Full Fill
        filled_qty = await self._get_filled_quantity(order_id)
        
        if filled_qty is None:
            logger.warning(f"Failed to confirm fill for {order_id}. Assuming zero fill to protect margin.")
            return False
            
        if filled_qty == 0:
            logger.warning(f"IOC Order {order_id} CANCELLED by exchange (Zero Fill). Aborting Stop Loss.")
            return False
            
        if filled_qty < quantity:
            logger.warning(f"PARTIAL FILL DETECTED: Requested {quantity}, Filled {filled_qty}.")
            # The mathematical edge (EV) is destroyed by fixed flat-fee transactional costs on undersized fills.
            # We must instantly liquidate the partial fill at market to avoid trading a guaranteed negative-EV position.
            logger.critical(f"EV DESTROYED: Liquidating partial fill ({filled_qty} units) at MARKET instantly.")
            
            liquidation_payload = {
                "quantity": filled_qty,
                "product": "I", 
                "validity": "DAY",
                "price": 0,
                "tag": "alpha_engine_liquidation",
                "instrument_token": instrument_token,
                "order_type": "MARKET",
                "transaction_type": "SELL" if transaction_type == "BUY" else "BUY",
                "disclosed_quantity": 0,
                "trigger_price": 0,
                "is_amo": False
            }
            await self._post_order(liquidation_payload)
            return False
        else:
            logger.success(f"ENTRY COMPLETELY FILLED for {instrument_token} ({filled_qty} units).")
        
        # 2. Instantly Fire Stop-Loss Order to Offload Risk for FULL filled quantity
        sl_transaction_type = "SELL" if transaction_type == "BUY" else "BUY"
        # SL limit price is slightly worse than trigger price to ensure fill during fast moves
        sl_limit_buffer = 0.05 * stop_price  # 5% buffer on options SL limit
        sl_limit_price = round(stop_price - sl_limit_buffer if sl_transaction_type == "SELL" else stop_price + sl_limit_buffer, 2)
        
        sl_payload = {
            "quantity": filled_qty,  # Use dynamically polled filled quantity
            "product": "I", 
            "validity": "DAY",
            "price": sl_limit_price,
            "tag": "alpha_engine_sl",
            "instrument_token": instrument_token,
            "order_type": "SL",
            "transaction_type": sl_transaction_type,
            "disclosed_quantity": 0,
            "trigger_price": stop_price,
            "is_amo": False
        }
        
        sl_result = await self._post_order(sl_payload)
        
        if not sl_result or sl_result.get("status") != "success":
            logger.critical(f"EXECUTOR RISK WARNING: Entry placed, but Stop Loss failed for {instrument_token}!")
            return False
            
        logger.success(f"RISK OFFLOADED: Stop loss placed for {instrument_token} at Trigger {stop_price}.")
        return True
