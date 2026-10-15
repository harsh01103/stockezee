import pytest
from market.decoder import ProtobufDecoder
from market.proto import MarketDataFeed_pb2 as pb

def test_decoder_success_rate():
    decoder = ProtobufDecoder()
    
    # Create valid dummy payload
    feed_response = pb.FeedResponse()
    feed_response.type = pb.FeedResponse.live_feed
    
    feed = feed_response.feeds["NSE_FO|NIFTY24JUN23000CE"]
    feed.fullFeed.ltp = 150.5
    feed.fullFeed.oi = 12000
    feed.fullFeed.vtt = 500
    
    # Empty market level for quotes
    feed.fullFeed.marketLevel.bidAskQuote.add(bp=150.0, bq=50, ap=151.0, aq=50)
    
    payload = feed_response.SerializeToString()
    
    # Decode
    ticks = decoder.decode(payload)
    
    assert len(ticks) == 1
    assert ticks[0].ltp == 150.5
    assert ticks[0].underlying == "NIFTY"
    assert ticks[0].bid == 150.0
    assert ticks[0].ask == 151.0
    
    assert decoder.metrics.decode_success_rate == 100.0
    
    # Test failure
    decoder.decode(b"invalid_protobuf_bytes_here")
    assert decoder.metrics.decode_failures == 1
    assert decoder.metrics.decode_success_rate == 50.0 # 1 success / 2 attempts
