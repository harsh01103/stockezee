import json
import time
import base64
import asyncio
import threading
import httpx
import websocket
from loguru import logger
from typing import Callable, List, Optional

class UpstoxWSClient:
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        self.is_connected = False
        self.should_reconnect = True
        self.on_message_callback: Optional[Callable[[bytes], None]] = None
        self.on_disconnect_callback: Optional[Callable[[], None]] = None

    async def _get_ws_uri(self) -> str:
        """Fetch the authorized WebSocket URI from Upstox."""
        token = self.auth_manager.get_access_token()
        if not token:
            raise ValueError("No valid access token available for WebSocket.")
            
        url = "https://api.upstox.com/v2/feed/market-data-feed/authorize"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 401:
                meta = self.auth_manager.store.get_token_meta()
                age = time.time() - meta.created_at if meta else -1
                expiry = meta.expires_at if meta else -1
                
                safe_headers = dict(headers)
                safe_headers["Authorization"] = "Bearer ***"
                
                logger.error(f"WS Auth 401! Token age: {age:.1f}s, expiry: {expiry}. Headers: {safe_headers}")
                
                logger.info("Attempting silent refresh due to WS 401...")
                refresh_result = await self.auth_manager.silent_refresh()
                logger.info(f"Refresh result: {refresh_result}")
                
                if refresh_result:
                    token = self.auth_manager.get_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    response = await client.get(url, headers=headers)
                    
            response.raise_for_status()
            data = response.json()
            return data["data"]["authorized_redirect_uri"]

    def _on_message(self, ws, message):
        """Handle incoming binary protobuf message."""
        if self.on_message_callback:
            self.on_message_callback(message)

    def _on_error(self, ws, error):
        logger.error(f"Upstox WebSocket Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"Upstox WebSocket Disconnected: {close_status_code} - {close_msg}")
        self.is_connected = False
        if self.on_disconnect_callback:
            self.on_disconnect_callback()

    def _on_open(self, ws):
        logger.info("Upstox WebSocket Connected.")
        self.is_connected = True

    async def connect(self):
        """Establish the WebSocket connection."""
        self.should_reconnect = True
        try:
            uri = await self._get_ws_uri()
        except Exception as e:
            logger.error(f"Failed to get WS URI: {e}")
            raise
            
        self.ws = websocket.WebSocketApp(
            uri,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()
        
        # Wait for connection to establish
        for _ in range(50):
            if self.is_connected:
                break
            await asyncio.sleep(0.1)

    def subscribe(self, instrument_keys: List[str]):
        """Subscribe to a list of instrument keys."""
        if not self.is_connected or not self.ws:
            logger.warning("Cannot subscribe, WebSocket not connected.")
            return
            
        payload = {
            "guid": "sub_1",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": instrument_keys
            }
        }
        self.ws.send(json.dumps(payload).encode('utf-8'))
        logger.debug(f"Sent subscription for {len(instrument_keys)} instruments.")

    def unsubscribe(self, instrument_keys: List[str]):
        """Unsubscribe from a list of instrument keys."""
        if not self.is_connected or not self.ws:
            return
            
        payload = {
            "guid": "unsub_1",
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        self.ws.send(json.dumps(payload).encode('utf-8'))
        logger.debug(f"Sent unsubscription for {len(instrument_keys)} instruments.")

    def close(self):
        """Close the WebSocket connection."""
        self.should_reconnect = False
        if self.ws:
            self.ws.close()
        if self.ws_thread:
            self.ws_thread.join(timeout=2.0)
