import pytest
from market.decoder import ProtobufDecoder, FeedType
from market.proto import MarketDataFeed_pb2 as pb

def test_ltpc_decode():
    decoder = ProtobufDecoder()
    
    feed_response = pb.FeedResponse()
    feed_response.type = pb.FeedResponse.live_feed
    
    feed = feed_response.feeds["NSE_FO|NIFTY24JUN23000CE"]
    feed.ltpc.ltp = 150.5
    feed.ltpc.ltt = 1620000000000
    
    payload = feed_response.SerializeToString()
    ticks = decoder.decode(payload)
    
    assert len(ticks) == 1
    assert ticks[0].feed_type == FeedType.LTPC.value
    assert ticks[0].ltp == 150.5
    assert "bid" in ticks[0].missing_fields
    assert decoder.metrics.ltpc_count == 1
