import time
from loguru import logger
from typing import List, Optional
from enum import Enum

from market.proto import MarketDataFeedV3_pb2 as pb
from market.schema import MarketTick

class FeedType(str, Enum):
    LTPC = "LTPC"
    FULL_FEED = "FULL_FEED"
    INDEX_FF = "INDEX_FF"
    OPTION_GREEKS = "OPTION_GREEKS"
    UNKNOWN = "UNKNOWN"

class DecoderMetrics:
    def __init__(self):
        self.decode_success_rate = 0.0
        self.decode_failures = 0
        self.total_decoded = 0
        self.total_attempted = 0
        self.unknown_feeds = 0
        self.ltpc_count = 0
        self.full_feed_count = 0

class ProtobufDecoder:
    def __init__(self, instrument_resolver=None):
        self.metrics = DecoderMetrics()
        self.instrument_resolver = instrument_resolver
        self.state = {}  # Cache for merging delta payloads

    def decode(self, payload: bytes) -> List[MarketTick]:
        """Decode raw binary payload to list of MarketTicks."""
        self.metrics.total_attempted += 1
        ticks = []
        try:
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(payload)
            
            for instrument_key, feed in feed_response.feeds.items():
                feed_type = FeedType.UNKNOWN
                if instrument_key not in self.state:
                    self.state[instrument_key] = {"ltp": 0.0, "ltt": 0, "bid": 0.0, "ask": 0.0, "volume": 0, "oi": 0, "obi": 0.0}
                
                state = self.state[instrument_key]
                missing = []
                
                if feed.HasField("ltpc"):
                    feed_type = FeedType.LTPC
                    self.metrics.ltpc_count += 1
                    ltpc = feed.ltpc
                    if ltpc.ltp: state["ltp"] = ltpc.ltp
                    if ltpc.ltt: state["ltt"] = ltpc.ltt
                    missing.extend(["bid", "ask", "volume", "oi"])
                    
                if feed.HasField("fullFeed"):
                    feed_type = FeedType.FULL_FEED
                    self.metrics.full_feed_count += 1
                    ff = feed.fullFeed
                    
                    if ff.HasField("marketFF"):
                        mff = ff.marketFF
                        if mff.HasField("ltpc"):
                            if mff.ltpc.ltp: state["ltp"] = mff.ltpc.ltp
                            if mff.ltpc.ltt: state["ltt"] = int(mff.ltpc.ltt)
                        if mff.vtt: state["volume"] = int(mff.vtt)
                        if mff.oi: state["oi"] = float(mff.oi)
                        
                        if mff.HasField("marketLevel") and len(mff.marketLevel.bidAskQuote) > 0:
                            # Extract Level 1 quotes for spread/pricing
                            quote = mff.marketLevel.bidAskQuote[0]
                            if quote.bidP: state["bid"] = quote.bidP
                            if quote.askP: state["ask"] = quote.askP
                            
                            # Calculate Order Book Imbalance (OBI) across all available levels (up to 5)
                            sum_bid_q = 0
                            sum_ask_q = 0
                            for q in mff.marketLevel.bidAskQuote:
                                if q.bidQ: sum_bid_q += q.bidQ
                                if q.askQ: sum_ask_q += q.askQ
                            if (sum_bid_q + sum_ask_q) > 0:
                                state["obi"] = (sum_bid_q - sum_ask_q) / (sum_bid_q + sum_ask_q)
                        else:
                            missing.extend(["bid", "ask", "obi"])
                            
                    elif ff.HasField("indexFF"):
                        iff = ff.indexFF
                        if iff.HasField("ltpc"):
                            if iff.ltpc.ltp: state["ltp"] = iff.ltpc.ltp
                            if iff.ltpc.ltt: state["ltt"] = int(iff.ltpc.ltt)
                        missing.extend(["bid", "ask"])
                        
                    else:
                        missing.extend(["bid", "ask", "volume", "oi"])
                        
                elif feed.HasField("optionGreeks"):
                    feed_type = FeedType.OPTION_GREEKS
                    missing.extend(["ltp", "bid", "ask", "volume", "oi"])
                    
                else:
                    self.metrics.unknown_feeds += 1
                    continue
                
                ltp = state["ltp"]
                ltt = state["ltt"]
                bid = state["bid"]
                ask = state["ask"]
                volume = state["volume"]
                oi = state["oi"]
                obi = state["obi"]
                    
                underlying = "UNKNOWN"
                expiry = ""
                strike = 0.0
                option_type = ""
                
                # Reverse lookup from cache
                hit = False
                if self.instrument_resolver:
                    identity = self.instrument_resolver.resolve_from_key(instrument_key)
                    if identity:
                        hit = True
                        underlying = identity.get("underlying", underlying)
                        expiry = identity.get("expiry", expiry)
                        strike = float(identity.get("strike", strike))
                        option_type = identity.get("option_type", option_type)
                        
                # Fallback regex parsing if resolver failed
                if not hit and "|" in instrument_key:
                    parts = instrument_key.split("|")[1]
                    import re
                    # Format e.g. BANKNIFTY24062656300CE or NIFTY24JUN24000CE
                    match = re.match(r'^([A-Z]+)(\d{2}[A-Z]{3}|\d{6})(\d+)(CE|PE)$', parts)
                    if match:
                        underlying = match.group(1)
                        expiry_str = match.group(2)
                        if len(expiry_str) == 5:
                            day = expiry_str[:2]
                            month_str = expiry_str[2:]
                            months = {"JAN":"01", "FEB":"02", "MAR":"03", "APR":"04", "MAY":"05", "JUN":"06", "JUL":"07", "AUG":"08", "SEP":"09", "OCT":"10", "NOV":"11", "DEC":"12"}
                            month = months.get(month_str, "01")
                            expiry = f"2026-{month}-{day}"
                        elif len(expiry_str) == 6:
                            year = "20" + expiry_str[:2]
                            month = expiry_str[2:4]
                            day = expiry_str[4:]
                            expiry = f"{year}-{month}-{day}"
                        else:
                            expiry = expiry_str
                        strike = float(match.group(3))
                        option_type = match.group(4)
                    else:
                        parts_upper = parts.upper()
                        if parts_upper.startswith("BANKNIFTY") or "NIFTY BANK" in parts_upper: underlying = "BANKNIFTY"
                        elif parts_upper.startswith("NIFTY") or "NIFTY 50" in parts_upper: underlying = "NIFTY"
                        elif "FINNIFTY" in parts_upper: underlying = "FINNIFTY"
                        
                ticks.append(MarketTick(
                    timestamp=time.time() * 1000,
                    exchange_timestamp=float(ltt) if ltt else time.time() * 1000,
                    underlying=underlying,
                    expiry=expiry,
                    strike=strike,
                    option_type=option_type,
                    spot=0.0,
                    ltp=ltp,
                    bid=bid,
                    ask=ask,
                    volume=volume,
                    oi=oi,
                    obi=obi,
                    source="upstox",
                    latency_ms=0.0,
                    record_id=instrument_key,
                    feed_type=feed_type.value,
                    missing_fields=missing
                ))
                    
            self.metrics.total_decoded += 1
            self._update_metrics()
            return ticks
            
        except Exception as e:
            self.metrics.decode_failures += 1
            self._update_metrics()
            logger.debug(f"Failed to decode protobuf payload: {e}")
            return []
            
    def _update_metrics(self):
        if self.metrics.total_attempted > 0:
            self.metrics.decode_success_rate = (self.metrics.total_decoded / self.metrics.total_attempted) * 100
