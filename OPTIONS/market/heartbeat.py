import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any

from auth.auth_manager import AuthManager
from market.validator import MarketValidator
from market.storage import StorageManager

RUNTIME_DIR = Path("runtime")

class HeartbeatMonitor:
    def __init__(self, auth_manager: AuthManager, validator: MarketValidator, storage: StorageManager, recorder: Any = None):
        self.auth_manager = auth_manager
        self.validator = validator
        self.storage = storage
        self.recorder = recorder
        self.is_running = False
        
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self.heartbeat_file = RUNTIME_DIR / "heartbeat.json"

    async def _heartbeat_loop(self):
        # Initial token validation via REST
        start_val = time.time()
        auth_validated = await self.auth_manager.validate_token_rest()
        token_validation_ms = (time.time() - start_val) * 1000
        
        if not auth_validated:
            import loguru
            loguru.logger.warning("REST validation failed. Attempting silent refresh...")
            refresh_success = await self.auth_manager.silent_refresh()
            if not refresh_success:
                loguru.logger.error("Silent refresh failed. Stopping recorder.")
                import sys
                self.is_running = False
                if self.recorder:
                    self.recorder.is_running = False
                import os
                os._exit(1)
            else:
                auth_validated = True

        while self.is_running:
            try:
                # Calculate p95 latency
                latency_p95 = 0.0
                if self.validator.latencies:
                    import statistics
                    try:
                        latency_p95 = statistics.quantiles(self.validator.latencies[-100:], n=100)[94]
                    except statistics.StatisticsError:
                        latency_p95 = sum(self.validator.latencies[-100:]) / len(self.validator.latencies[-100:])
                
                # Check rows buffered
                rows_buffered = len(self.storage.tick_buffer)
                
                # Check auth state
                auth_meta = self.auth_manager.store.get_token_meta()
                auth_state = auth_meta.state.value if auth_meta else "UNKNOWN"
                
                is_ws_connected = self.recorder.provider.is_connected if self.recorder else False
                active_subs = len(self.recorder.current_subscriptions) if self.recorder else 0
                messages_received = self.validator.messages_received
                
                healthy = True
                if auth_state != "VALID" or not auth_validated:
                    healthy = False
                if not is_ws_connected:
                    healthy = False
                if active_subs == 0:
                    healthy = False
                if messages_received == 0:
                    healthy = False
                if rows_buffered == 0:
                    healthy = False
                
                status_data = {
                    "status": "healthy" if healthy else "unhealthy",
                    "last_tick": time.time(),
                    "latency_p95": latency_p95,
                    "rows_buffered": rows_buffered,
                    "messages_received": messages_received,
                    "auth_state": auth_state,
                    "auth_validated": auth_validated,
                    "token_validation_ms": round(token_validation_ms, 2)
                }
                
                # Write to file atomically
                temp_file = self.heartbeat_file.with_suffix(".tmp")
                with open(temp_file, "w") as f:
                    json.dump(status_data, f, indent=2)
                temp_file.replace(self.heartbeat_file)
                
            except Exception as e:
                import loguru
                loguru.logger.error(f"Heartbeat error: {e}")
                
            await asyncio.sleep(5)

    def start(self) -> asyncio.Task:
        self.is_running = True
        return asyncio.create_task(self._heartbeat_loop())
        
    def stop(self):
        self.is_running = False
