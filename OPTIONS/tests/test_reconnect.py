import pytest
from unittest.mock import MagicMock
from market.recorder import MarketRecorder
from auth.auth_manager import AuthManager

def test_reconnect_logic():
    auth_manager = MagicMock(spec=AuthManager)
    recorder = MarketRecorder(auth_manager)
    
    # Simulate a disconnect event
    recorder._on_ws_disconnect()
    
    assert recorder.validator.reconnect_count == 1
    # Check that should_reconnect is True in WS client
    assert recorder.ws_client.should_reconnect is True
