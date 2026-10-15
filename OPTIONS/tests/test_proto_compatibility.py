import pytest
from market.proto import MarketDataFeed_pb2 as pb

def test_proto_fields_exist():
    # Verify the compiled protobuf has the expected schema fields
    ff = pb.FullFeed()
    assert hasattr(ff, "ltp")
    assert hasattr(ff, "vtt")
    assert hasattr(ff, "oi")
    assert hasattr(ff, "marketLevel")
    
    quote = pb.Quote()
    assert hasattr(quote, "bp")
    assert hasattr(quote, "ap")
