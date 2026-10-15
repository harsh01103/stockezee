import pytest
import time
import json
from unittest.mock import MagicMock, AsyncMock, patch
from auth.schema import TokenState, TokenMeta

@pytest.mark.asyncio
async def test_silent_refresh():
    """Test that silent_refresh calls refresh_access_token and updates token state."""
    # We need to patch AuthManager's __init__ since it reads from .env
    with patch("auth.auth_manager.TokenStore") as MockStore, \
         patch("auth.auth_manager.UpstoxAuthClient") as MockClient, \
         patch.dict("os.environ", {
             "UPSTOX_API_KEY": "test_key",
             "UPSTOX_API_SECRET": "test_secret",
             "UPSTOX_REDIRECT_URI": "http://localhost:8787",
             "TOKEN_ENCRYPTION_KEY": "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ9PQ=="
         }):
        from auth.auth_manager import AuthManager
        
        store_mock = MockStore.return_value
        client_mock = MockClient.return_value
        
        # Setup store to simulate a token nearing expiry
        meta_mock = MagicMock()
        meta_mock.state = TokenState.VALID
        meta_mock.expires_at = time.time() + 1800  # 30 mins left (< 3600 threshold)
        store_mock.get_token_meta.return_value = meta_mock
        
        # get_token_payload returns JSON with refresh_token
        payload = json.dumps({"access_token": "old_acc", "refresh_token": "old_ref"})
        store_mock.get_token_payload.return_value = payload
        
        # Mock the refresh call
        client_mock.refresh_access_token = AsyncMock(return_value={
            "access_token": "new_acc",
            "refresh_token": "new_ref",
            "expires_in": 86400
        })
        
        manager = AuthManager()
        
        # Call silent_refresh directly
        result = await manager.silent_refresh()
        
        assert result == True
        
        # Verify refresh was called
        client_mock.refresh_access_token.assert_called_once_with("old_ref")
        
        # Verify state transitions
        store_mock.update_meta_state.assert_any_call(TokenState.REFRESHING)
        
        # Verify token was saved
        store_mock.save_token.assert_called_once()
