import pytest
from market.decoder import ProtobufDecoder, FeedType
from market.proto import MarketDataFeed_pb2 as pb

def test_feed_matrix():
    decoder = ProtobufDecoder()
    
    feed_response = pb.FeedResponse()
    
    # 1. LTPC
    feed1 = feed_response.feeds["NSE_FO|NIFTY24JUN23000CE"]
    feed1.ltpc.ltp = 100.0
    
    # 2. IndexFF
    feed2 = feed_response.feeds["NSE_INDEX|Nifty 50"]
    feed2.indexFF.ltp = 23000.0
    
    # 3. OptionGreeks
    feed3 = feed_response.feeds["NSE_FO|NIFTY24JUN23500PE"]
    feed3.optionGreeks.iv = 15.5
    
    payload = feed_response.SerializeToString()
    ticks = decoder.decode(payload)
    
    assert len(ticks) == 3
    feed_types = {t.feed_type for t in ticks}
    assert feed_types == {FeedType.LTPC.value, FeedType.INDEX_FF.value, FeedType.OPTION_GREEKS.value}
    assert decoder.metrics.unknown_feeds == 0
