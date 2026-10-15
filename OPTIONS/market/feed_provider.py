import abc
import json
import time
import asyncio
import threading
import httpx
import websocket
import yaml
from loguru import logger
from typing import List, Optional

class FeedProvider(abc.ABC):
    @abc.abstractmethod
    async def authorize(self) -> str:
        pass

    @abc.abstractmethod
    async def connect(self):
        pass

    @abc.abstractmethod
    def subscribe(self, instrument_keys: List[str]):
        pass

    @abc.abstractmethod
    def unsubscribe(self, instrument_keys: List[str]):
        pass

    @abc.abstractmethod
    async def receive(self):
        pass
        
    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        pass

    @property
    @abc.abstractmethod
    def should_reconnect(self) -> bool:
        pass
        
    @abc.abstractmethod
    def close(self):
        pass

class UpstoxProvider(FeedProvider):
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        self._is_connected = False
        self._should_reconnect = True
        self.queue = asyncio.Queue()
        self.on_disconnect_callback = None
        self.on_connect_callback = None
        
        # Load config
        with open("config/provider.yaml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.version = self.config.get("transport_version", "v3")
        self.upstox_config = self.config.get("upstox", {})

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def should_reconnect(self) -> bool:
        return self._should_reconnect

    async def authorize(self) -> str:
        """Execute the v3 authorize flow to get the redirect URI."""
        token = self.auth_manager.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers={"Authorization": f"Bearer {token}"})
            logger.info(f"authorize_http: {resp.status_code}")
            uri = resp.json().get("data", {}).get("authorizedRedirectUri")
            logger.info(f"redirect_uri_received: {bool(uri)}")
            if not uri:
                raise ValueError("Failed to obtain authorizedRedirectUri from Upstox")
            return uri

    def _on_message(self, ws, message):
        """Handle incoming binary protobuf message."""
        logger.info("DIAGNOSTICS: frames_received")
        if isinstance(message, str) or (isinstance(message, bytes) and len(message) > 0 and message[0:1] == b'{'):
            logger.info(f"DIAGNOSTICS: subscription_ack -> {message}")
        else:
            logger.info(f"DIAGNOSTICS: market_frames (len={len(message)})")

        # Use run_coroutine_threadsafe since this is called from the websocket thread
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.queue.put(message), loop)
        except RuntimeError:
            # If no running loop in this thread, we need the main loop. 
            # We will store the loop during connect()
            if hasattr(self, 'main_loop'):
                asyncio.run_coroutine_threadsafe(self.queue.put(message), self.main_loop)
            else:
                logger.error("No event loop available to process WS message")

    def _on_error(self, ws, error):
        logger.error(f"Upstox WebSocket Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"Upstox WebSocket Disconnected: {close_status_code} - {close_msg}")
        self._is_connected = False
        if self.on_disconnect_callback:
            if hasattr(self, 'main_loop'):
                self.main_loop.call_soon_threadsafe(self.on_disconnect_callback)
            else:
                self.on_disconnect_callback()

    def _on_open(self, ws):
        logger.info("Upstox WebSocket Connected.")
        logger.info("DIAGNOSTICS: ws_connected=True")
        self._is_connected = True
        
        # Upstox V3 Market Data Feed silently drops subscriptions if sent immediately
        import time
        time.sleep(1.0)

        # Request subscription for active symbols
        if self.on_connect_callback:
            self.on_connect_callback()

    async def connect(self):
        """Establish the WebSocket connection."""
        self.main_loop = asyncio.get_running_loop()
        self._should_reconnect = True
        logger.info("ws_connect_started")
        try:
            uri = await self.authorize()
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
            if self._is_connected:
                logger.info("ws_connect_success")
                break
            await asyncio.sleep(0.1)

    def subscribe(self, instrument_keys: List[str]):
        """Subscribe to a list of instrument keys."""
        if not self._is_connected or not self.ws:
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
        logger.info(f"DIAGNOSTICS: subscription_payload={json.dumps(payload)}")
        self.ws.send(json.dumps(payload).encode('utf-8'), opcode=websocket.ABNF.OPCODE_BINARY)
        logger.debug(f"Sent subscription for {len(instrument_keys)} instruments.")

    def unsubscribe(self, instrument_keys: List[str]):
        """Unsubscribe from a list of instrument keys."""
        if not self._is_connected or not self.ws:
            return
            
        payload = {
            "guid": "unsub_1",
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        import websocket
        self.ws.send(json.dumps(payload).encode('utf-8'), opcode=websocket.ABNF.OPCODE_BINARY)
        logger.debug(f"Sent unsubscription for {len(instrument_keys)} instruments.")

    async def receive(self):
        """Async generator yielding incoming messages."""
        while self._should_reconnect or not self.queue.empty():
            msg = await self.queue.get()
            yield msg

    def close(self, permanent=False):
        """Close the WebSocket connection.
        
        Args:
            permanent: If True, disable reconnect permanently (full shutdown).
                       If False, close socket but allow reconnect.
        """
        if permanent:
            self._should_reconnect = False
        if self.ws:
            self.ws.close()
        if self.ws_thread:
            self.ws_thread.join(timeout=2.0)
