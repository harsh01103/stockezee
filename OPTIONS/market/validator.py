import json
import statistics
from pathlib import Path
from loguru import logger
from typing import List, Dict, Optional
from cachetools import LRUCache

from market.schema import MarketTick

REPORTS_DIR = Path("reports")

class MarketValidator:
    def __init__(self):
        self.messages_received = 0
        self.total_received = 0
        self.total_dropped = 0
        self.latencies: List[float] = []
        self.reconnect_count = 0
        self.token_refresh_count = 0
        
        self.drop_reasons: Dict[str, int] = {
            "duplicate": 0,
            "negative_value": 0,
            "missing_timestamp": 0,
            "bid_gt_ask": 0
        }
        self.warning_reasons: Dict[str, int] = {
            "oi_reset": 0
        }
        
        # Max size 100k covers over 15 mins of heavy tick volume
        self.seen_record_ids = LRUCache(maxsize=100000)
        self.last_oi: Dict[str, int] = {}
        
        REPORTS_DIR.mkdir(exist_ok=True)

    def validate(self, tick: MarketTick) -> bool:
        """Validates a tick. Returns True if valid, False if it should be dropped."""
        self.total_received += 1
        
        if not tick.timestamp or not tick.exchange_timestamp:
            self.drop_reasons["missing_timestamp"] += 1
            self.total_dropped += 1
            logger.warning(f"Drop: missing_timestamp for {tick.underlying}")
            return False

        if tick.record_id in self.seen_record_ids:
            self.drop_reasons["duplicate"] += 1
            self.total_dropped += 1
            return False
            
        if tick.spot < 0 or tick.ltp < 0 or tick.bid < 0 or tick.ask < 0 or tick.volume < 0:
            self.drop_reasons["negative_value"] += 1
            self.total_dropped += 1
            logger.warning(f"Drop: negative_value for {tick.underlying}")
            return False
            
        if tick.bid > tick.ask and tick.ask > 0:
            self.drop_reasons["bid_gt_ask"] += 1
            self.total_dropped += 1
            logger.warning(f"Drop: bid_gt_ask ({tick.bid} > {tick.ask}) for {tick.underlying}")
            return False

        # OI Reset check
        instrument_key = f"{tick.underlying}_{tick.strike}_{tick.option_type}"
        last_oi_val = self.last_oi.get(instrument_key)
        
        if last_oi_val is not None and tick.oi < (last_oi_val * 0.1) and tick.oi == 0:
            self.warning_reasons["oi_reset"] += 1
            logger.warning(f"Warning: oi_reset for {instrument_key}")
            
        self.last_oi[instrument_key] = tick.oi
        
        # Valid tick
        self.seen_record_ids[tick.record_id] = True
        self.latencies.append(tick.latency_ms)
        
        return True

    def generate_report(self, session_id: str):
        """Generates the session report with latency, packet loss, and reconnect metrics."""
        latency_p95 = 0.0
        if self.latencies:
            try:
                # Approximate P95
                latency_p95 = statistics.quantiles(self.latencies, n=100)[94]
            except statistics.StatisticsError:
                latency_p95 = sum(self.latencies) / len(self.latencies)
                
        packet_loss = 0.0
        if self.total_received > 0:
            packet_loss = self.total_dropped / self.total_received

        report = {
            "session_id": session_id,
            "metrics": {
                "total_received": self.total_received,
                "total_dropped": self.total_dropped,
                "packet_loss_pct": packet_loss * 100,
                "latency_p95_ms": latency_p95,
                "reconnect_count": self.reconnect_count,
                "token_refresh_count": self.token_refresh_count
            },
            "drop_reasons": self.drop_reasons,
            "warning_reasons": self.warning_reasons
        }
        
        report_path = REPORTS_DIR / f"session_report_{session_id}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Session report generated: {report_path}")
