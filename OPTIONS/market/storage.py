import time
import base64
import uuid
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger
from typing import List, Dict, Any
from asyncio import Lock

from market.schema import MarketTick

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
EVENTS_DIR = DATA_DIR / "events"

class StorageManager:
    def __init__(self, dry_run: bool = False):
        self.tick_buffer: List[MarketTick] = []
        self.event_buffer: List[Dict[str, Any]] = []
        self.dry_run = dry_run
        self.tick_lock = Lock()
        self.event_lock = Lock()
        self.rows_written_virtual = 0
        self.flush_count = 0
        
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    async def add_tick(self, tick: MarketTick):
        if tick.source_type == "MOCK":
            logger.warning(f"Rejecting MOCK tick")
            return
        async with self.tick_lock:
            self.tick_buffer.append(tick)

    async def add_raw_event(self, source: str, payload_bytes: bytes):
        if self.dry_run:
            return
            
        event = {
            "source": source,
            "received_at": datetime.now(timezone.utc).isoformat(),
            # If payload is binary (Upstox v2 protobuf), store as base64
            "payload": base64.b64encode(payload_bytes).decode('utf-8')
        }
        async with self.event_lock:
            self.event_buffer.append(event)

    def _get_minute_path(self, base_dir: Path, dt: datetime, ext: str) -> Path:
        date_str = dt.strftime("%Y-%m-%d")
        minute_str = dt.strftime("%H_%M")
        
        day_dir = base_dir / date_str
        day_dir.mkdir(exist_ok=True)
        
        unique_id = uuid.uuid4().hex[:6]
        return day_dir / f"{minute_str}_{unique_id}{ext}"

    async def flush(self):
        """Flush buffers to Parquet using zstd compression."""
        if self.dry_run:
            self.flush_count += 1
            MAX_DRY_ROWS = 10000
            async with self.tick_lock:
                self.rows_written_virtual += len(self.tick_buffer)
                if len(self.tick_buffer) > MAX_DRY_ROWS:
                    self.tick_buffer = self.tick_buffer[-MAX_DRY_ROWS:]
            async with self.event_lock:
                if len(self.event_buffer) > MAX_DRY_ROWS:
                    self.event_buffer = self.event_buffer[-MAX_DRY_ROWS:]
            return
            
        now = datetime.now(timezone.utc)
        
        # Flush Ticks
        ticks_to_flush = []
        async with self.tick_lock:
            if self.tick_buffer:
                ticks_to_flush = self.tick_buffer
                self.tick_buffer = []
                
        if ticks_to_flush:
            try:
                df = pl.DataFrame([t.model_dump() for t in ticks_to_flush])
                out_path = self._get_minute_path(RAW_DIR, now, ".parquet")
                # Write parquet with zstd
                df.write_parquet(out_path, compression="zstd")
                logger.debug(f"Flushed {len(ticks_to_flush)} ticks to {out_path.name}")
            except Exception as e:
                logger.error(f"Failed to flush ticks: {e}")
                # Requeue on failure to avoid data loss
                async with self.tick_lock:
                    self.tick_buffer = ticks_to_flush + self.tick_buffer

        # Flush Events
        events_to_flush = []
        async with self.event_lock:
            if self.event_buffer:
                events_to_flush = self.event_buffer
                self.event_buffer = []
                
        if events_to_flush:
            try:
                df = pl.DataFrame(events_to_flush)
                out_path = self._get_minute_path(EVENTS_DIR, now, ".parquet")
                df.write_parquet(out_path, compression="zstd")
                logger.debug(f"Flushed {len(events_to_flush)} events to {out_path.name}")
            except Exception as e:
                logger.error(f"Failed to flush events: {e}")
                async with self.event_lock:
                    self.event_buffer = events_to_flush + self.event_buffer

    def cleanup_old_events(self, days=7):
        """Deletes raw events older than `days`."""
        now = time.time()
        for day_dir in EVENTS_DIR.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                dir_date = datetime.strptime(day_dir.name, "%Y-%m-%d")
                if (now - dir_date.timestamp()) > (days * 86400):
                    logger.info(f"Removing old events directory: {day_dir}")
                    for file in day_dir.iterdir():
                        file.unlink()
                    day_dir.rmdir()
            except ValueError:
                pass
