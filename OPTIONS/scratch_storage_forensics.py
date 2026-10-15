import asyncio
import json
import time
from loguru import logger
from market.recorder import MarketRecorder
from market.validator import MarketValidator
from market.storage import StorageManager
from market.schema import MarketTick
from dotenv import load_dotenv

load_dotenv(override=True)

# Counters
decoded_rows = 0
validator_received = 0
validator_rejected = 0
validator_passed = 0
storage_received = 0
storage_buffered = 0
storage_flushed = 0

add_tick_called = 0
buffer_size_before = 0
buffer_size_after = 0
flush_called = 0
flush_skipped = 0

rejected_rows_log = []
drop_reasons_counts = {}

# Mock the _process_queue of recorder to trace the lifecycle
original_process_queue = MarketRecorder._process_queue

async def hooked_process_queue(self):
    global decoded_rows, validator_received, validator_rejected, validator_passed
    global storage_received, storage_buffered, add_tick_called

    while self.is_running:
        message = await self.queue.get()
        if message is None:
            break
            
        try:
            ticks = self.decoder.decode(message)
            decoded_rows += len(ticks)
            
            for tick in ticks:
                validator_received += 1
                valid = self.validator.validate(tick)
                if valid:
                    validator_passed += 1
                    storage_received += 1
                    add_tick_called += 1
                    await self.storage.add_tick(tick)
                    storage_buffered += 1
                else:
                    validator_rejected += 1
                    if len(rejected_rows_log) < 100:
                        reason = "unknown"
                        for r, c in self.validator.drop_reasons.items():
                            if c > drop_reasons_counts.get(r, 0):
                                reason = r
                                drop_reasons_counts[r] = c
                                break
                        rejected_rows_log.append({
                            "reason": reason,
                            "record_id": tick.record_id,
                            "instrument_key": tick.instrument_key if hasattr(tick, "instrument_key") else tick.underlying,
                            "timestamp": tick.timestamp,
                            "ltp": tick.ltp,
                            "bid": tick.bid,
                            "ask": tick.ask,
                            "volume": tick.volume,
                            "oi": tick.oi
                        })
        except Exception as e:
            logger.error(f"Error processing message: {e}")

# Mock storage flush
original_flush = StorageManager.flush

async def hooked_flush(self):
    global flush_called, flush_skipped, storage_flushed, buffer_size_before, buffer_size_after
    flush_called += 1
    
    async with self.tick_lock:
        buffer_size_before = len(self.tick_buffer)
    
    if self.dry_run:
        flush_skipped += 1
        # The exact behavior of dry_run flush is what we are auditing
        
    await original_flush(self)
    
    async with self.tick_lock:
        buffer_size_after = len(self.tick_buffer)
        storage_flushed += (buffer_size_before - buffer_size_after)

async def monitor():
    while True:
        await asyncio.sleep(5)
        print(f"[5s Trace] decoded={decoded_rows} val_recv={validator_received} val_pass={validator_passed} "
              f"val_rej={validator_rejected} sto_recv={storage_received} sto_buf={storage_buffered} sto_flush={storage_flushed}")
        print(f"[Storage Audit] dry_run=True add_tick_called={add_tick_called} buf_before={buffer_size_before} "
              f"buf_after={buffer_size_after} flush_called={flush_called} flush_skipped={flush_skipped}")

async def main():
    MarketRecorder._process_queue = hooked_process_queue
    StorageManager.flush = hooked_flush
    
    recorder = MarketRecorder(dry_run=True)
    
    task = asyncio.create_task(recorder.start())
    mon = asyncio.create_task(monitor())
    
    await asyncio.sleep(30)
    recorder.stop()
    await task
    mon.cancel()

    print("\n--- REJECTED ROWS (First 100) ---")
    for r in rejected_rows_log:
        print(r)
    
    print("\n--- DROP REASONS ---")
    print(drop_reasons_counts)
    
    print("\n--- FINAL COUNTS ---")
    print(f"decoded_rows: {decoded_rows}")
    print(f"validator_passed: {validator_passed}")
    print(f"validator_rejected: {validator_rejected}")
    print(f"rows_buffered: {len(recorder.storage.tick_buffer)}")
    print(f"rows_written: {storage_flushed if not recorder.storage.dry_run else 0}")
    
    # Check if dry_run bypasses add_tick
    bypass = (add_tick_called == 0 and validator_passed > 0)
    print(f"dry_run_bypasses_add_tick: {bypass}")

if __name__ == "__main__":
    asyncio.run(main())
