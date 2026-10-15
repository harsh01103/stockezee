import asyncio
import time
import uuid
import socket
from datetime import datetime
from loguru import logger
from typing import List

from auth.auth_manager import AuthManager
from auth.schema import TokenState
from market.nse_client import NSEClient
from market.strike_selector import StrikeSelector
import yaml
from market.feed_provider import FeedProvider, UpstoxProvider
from market.storage import StorageManager
from market.validator import MarketValidator
from market.schema import MarketTick
from market.heartbeat import HeartbeatMonitor
from market.decoder import ProtobufDecoder
from market.instrument_resolver import InstrumentResolver

class MarketRecorder:
    def __init__(self, auth_manager: AuthManager, session_id: str = None, dry_run: bool = False):
        self.auth_manager = auth_manager
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.nse_client = NSEClient(ttl_sec=20)
        self.strike_selector = StrikeSelector(self.nse_client)
        self.storage = StorageManager(dry_run=dry_run)
        self.validator = MarketValidator()
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = ("127.0.0.1", 5005)
        
        with open("config/provider.yaml", "r") as f:
            provider_config = yaml.safe_load(f)
            
        provider_name = provider_config.get("provider", "upstox")
        if provider_name == "upstox":
            self.provider = UpstoxProvider(self.auth_manager)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
            
        self.instrument_resolver = InstrumentResolver()
        self.decoder = ProtobufDecoder(instrument_resolver=self.instrument_resolver)
        self.heartbeat = HeartbeatMonitor(self.auth_manager, self.validator, self.storage, self)
        
        self.provider.on_disconnect_callback = self._on_ws_disconnect
        
        self.is_running = False
        self.current_subscriptions: List[str] = []
        self.metrics = {
            "subscription_attempts": 0,
            "subscription_success": 0,
            "subscription_failures": 0,
            "active_subscription_count": 0
        }

    def _on_ws_disconnect(self):
        self.validator.reconnect_count += 1
        logger.warning("Recorder noticed WS disconnect.")

    def _on_ws_message(self, message: bytes):
        """Handle incoming binary message from Upstox."""
        self.validator.messages_received += 1
        received_at_ms = time.time() * 1000
        
        # 1. Archive Raw Event BEFORE validation
        # Run in background to avoid blocking the WS read thread
        asyncio.run_coroutine_threadsafe(
            self.storage.add_raw_event("upstox", message),
            asyncio.get_event_loop()
        )
        
        # 2. Parse protobuf using the decoder
        parsed_ticks = self.decoder.decode(message)
        
        # 3. Validate and Store
        for tick in parsed_ticks:
            # Set the latency based on decode time
            tick.latency_ms = received_at_ms - tick.exchange_timestamp
            tick.record_id = uuid.uuid4().hex
            
            if self.validator.validate(tick):
                # 4. UDP Zero-Latency Broadcast to runner.py
                try:
                    payload = tick.model_dump_json().encode('utf-8')
                    self.udp_sock.sendto(payload, self.udp_addr)
                except Exception as e:
                    logger.debug(f"UDP send failed: {e}")
                    
                asyncio.run_coroutine_threadsafe(
                    self.storage.add_tick(tick),
                    asyncio.get_event_loop()
                )

    async def _message_receiver(self):
        """Consume messages from the provider asynchronously."""
        async for message in self.provider.receive():
            self._on_ws_message(message)

    async def _manage_subscriptions(self):
        """Update universe and sync WS subscriptions."""
        await self.instrument_resolver.ensure_loaded()
        while self.is_running:
            try:
                self.metrics["subscription_attempts"] += 1
                await self.strike_selector.update_universe()
                
                nifty_universe = self.strike_selector.get_selected_strikes("NIFTY")
                banknifty_universe = self.strike_selector.get_selected_strikes("BANKNIFTY")
                
                new_subs = []
                # Always add underlying index keys
                new_subs.extend(["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"])
                
                for item in nifty_universe + banknifty_universe:
                    underlying = "NIFTY" if "NIFTY" in str(item.get("underlying", "")) or item.get("underlyingValue") and len(nifty_universe) > 0 and item in nifty_universe else "BANKNIFTY"
                    if item.get("underlying"):
                         underlying = item.get("underlying")
                    
                    # Usually strike_selector passes the symbol, let's just infer from list membership
                    symbol = "NIFTY" if item in nifty_universe else "BANKNIFTY"
                    
                    strike = item.get("strikePrice")
                    expiry = item.get("expiryDate")
                    opt_type = item.get("optionType", "")
                    if not opt_type: # Fallback if optionType isn't explicitly set but we know it
                        # Wait, NSE payload separates CE and PE into dicts, but StrikeSelector returns the combined dict.
                        # We should generate both CE and PE if the item represents a strike
                        pass
                    
                    # Re-map correctly based on standard NSE Option Chain structure
                    ce_data = item.get("CE")
                    pe_data = item.get("PE")
                    
                    if ce_data:
                        ce_key = self.instrument_resolver.resolve(symbol, ce_data.get("expiryDate", expiry), ce_data.get("strikePrice", strike), "CE")
                        if ce_key: new_subs.append(ce_key)
                        
                    if pe_data:
                        pe_key = self.instrument_resolver.resolve(symbol, pe_data.get("expiryDate", expiry), pe_data.get("strikePrice", strike), "PE")
                        if pe_key: new_subs.append(pe_key)
                        
                    # If the item itself is flattened (like in fallback)
                    if item.get("optionType"):
                        flat_key = self.instrument_resolver.resolve(symbol, item.get("expiryDate"), item.get("strikePrice"), item.get("optionType"))
                        if flat_key: new_subs.append(flat_key)
                
                if len(new_subs) <= 2: # Only indices
                    self.metrics["subscription_failures"] += 1
                    logger.error("0 option subscriptions resolved! Rejecting.")
                    # Keep existing subscriptions or exit
                else:
                    old_set = set(self.current_subscriptions)
                    new_set = set(new_subs)
                    
                    to_unsubscribe = list(old_set - new_set)
                    to_subscribe = list(new_set - old_set)
                    
                    if to_unsubscribe or to_subscribe:
                        logger.info(f"Subscription update: +{len(to_subscribe)} / -{len(to_unsubscribe)}")
                        
                        if to_unsubscribe:
                            self.provider.unsubscribe(to_unsubscribe)
                            await asyncio.sleep(0.5)
                            
                        if to_subscribe:
                            self.provider.subscribe(to_subscribe)
                            
                        self.current_subscriptions = list(new_set)
                    
                    self.metrics["subscription_success"] += 1
                    self.metrics["active_subscription_count"] = len(self.current_subscriptions)
                    
            except Exception as e:
                self.metrics["subscription_failures"] += 1
                logger.error(f"Error managing subscriptions: {e}")
                
            await asyncio.sleep(60) # Refresh every 60s

    async def _storage_flusher(self):
        """Periodically flush storage to Parquet."""
        while self.is_running:
            await asyncio.sleep(15)  # 15s flush for ultra-low-latency signals
            try:
                await self.storage.flush()
            except Exception as e:
                logger.error(f"Storage flush failed: {e}")

    async def _connection_monitor(self):
        """Monitors WS connection and re-establishes if dropped."""
        while self.is_running:
            # Reconnect Logic
            token = await self.auth_manager.ensure_valid_token(interactive_allowed=False)
            if not token:
                logger.error("Failed to ensure valid token silently. Reconnect failed.")
                self.validator.token_refresh_count += 1
                self.provider.close(permanent=False)  # Keep reconnect enabled
                
                try:
                    # Normally would try refresh_token here, but for interactive fallback:
                    logger.info("Triggering interactive auth...")
                    await self.auth_manager.interactive_login()
                    logger.info("Re-auth successful. Resuming connection.")
                    # Force reconnect guard back on after successful auth
                    self.provider._should_reconnect = True
                    logger.info(f"WS_RECOVERY: token_valid=True should_reconnect={self.provider.should_reconnect}")
                except Exception as e:
                    logger.error(f"Re-auth failed. Waiting 30s before retry: {e}")
                    await asyncio.sleep(30)
                    continue
            
            # Check WS connection
            if not self.provider.is_connected and self.provider.should_reconnect:
                logger.info(f"WS_RECONNECT_ATTEMPT: Connecting {self.provider.__class__.__name__} WebSocket...")
                try:
                    await self.provider.connect()
                    # Resubscribe after reconnect
                    if self.current_subscriptions:
                        self.provider.subscribe(self.current_subscriptions)
                    logger.info(f"WS_RECONNECTED: subscriptions={len(self.current_subscriptions)}")
                except Exception as e:
                    logger.error(f"WebSocket connection failed: {e}")
                    await asyncio.sleep(5) # backoff
            
            await asyncio.sleep(5)

    async def start(self):
        """Start the market recorder session."""
        logger.info(f"Starting Market Recorder Session: {self.session_id}")
        self.is_running = True
        
        # Cleanup old events
        self.storage.cleanup_old_events(days=7)
        
        tasks = [
            asyncio.create_task(self._connection_monitor()),
            asyncio.create_task(self._manage_subscriptions()),
            asyncio.create_task(self._storage_flusher()),
            asyncio.create_task(self._message_receiver()),
            self.heartbeat.start()
        ]
        
        # Ingress Validation
        logger.info("Waiting for ingress validation...")
        startup_timeout = 300
        start_wait_time = time.time()
        validation_passed = False
        
        while time.time() - start_wait_time < startup_timeout:
            if (self.provider.is_connected and 
                len(self.current_subscriptions) > 0 and 
                self.validator.messages_received > 0):
                validation_passed = True
                break
            await asyncio.sleep(0.5)
            
        if not validation_passed:
            logger.error(f"Ingress validation failed. Connected: {self.provider.is_connected}, Subscriptions: {len(self.current_subscriptions)}, Messages: {self.validator.messages_received}")
            self.is_running = False
            self.heartbeat.stop()
            self.provider.close(permanent=True)
            await self.storage.flush()
            await self.nse_client.close()
            raise RuntimeError("Ingress validation failed. Refusing startup.")
            
        logger.info("Ingress validation passed. Recorder running.")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Recorder shutting down...")
        finally:
            self.is_running = False
            self.heartbeat.stop()
            self.provider.close(permanent=True)
            await self.storage.flush()
            await self.nse_client.close()
            self.validator.generate_report(self.session_id)
            logger.info(f"Session {self.session_id} ended.")
