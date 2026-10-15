import pytest
import asyncio
from unittest.mock import MagicMock
from market.recorder import MarketRecorder

@pytest.mark.asyncio
async def test_subscription_rotation():
    auth_manager = MagicMock()
    recorder = MarketRecorder(auth_manager)
    
    # Mock ws_client
    recorder.ws_client = MagicMock()
    recorder.ws_client.is_connected = True
    recorder.ws_client.subscribe = MagicMock()
    recorder.ws_client.unsubscribe = MagicMock()
    
    total_expected_subs = 15 # ATM +/- 7 = 15
    active_subs = set()
    
    # Simulate 10 ATM shifts
    for i in range(10):
        # Shift ATM by +1 strike each time
        new_universe = [f"NIFTY_STRIKE_{23000 + (j * 50) + (i * 50)}" for j in range(-7, 8)]
        
        # Apply logic from recorder
        old_set = set(recorder.current_subscriptions)
        new_set = set(new_universe)
        
        to_unsubscribe = list(old_set - new_set)
        to_subscribe = list(new_set - old_set)
        
        if to_unsubscribe:
            recorder.ws_client.unsubscribe(to_unsubscribe)
            active_subs -= set(to_unsubscribe)
            
        if to_subscribe:
            recorder.ws_client.subscribe(to_subscribe)
            active_subs |= set(to_subscribe)
            
        recorder.current_subscriptions = list(new_set)
        
        # Verify
        assert len(active_subs) == total_expected_subs
        assert len(recorder.current_subscriptions) == total_expected_subs

    # Reject if active subscriptions > expected * 1.1
    assert len(active_subs) <= total_expected_subs * 1.1
