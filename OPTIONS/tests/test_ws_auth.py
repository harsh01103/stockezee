import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from auth.auth_manager import AuthManager
from market.upstox_client import UpstoxWSClient
import httpx

@pytest.mark.asyncio
async def test_ws_auth_header_format():
    """Verify the Authorization header is sent in the exact 'Bearer {token}' format."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_access_token.return_value = "mock_token_123"
    
    ws_client = UpstoxWSClient(mock_auth_manager)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"authorized_redirect_uri": "wss://test.upstox.com"}}
        mock_get.return_value = mock_response
        
        uri = await ws_client._get_ws_uri()
        
        assert uri == "wss://test.upstox.com"
        mock_get.assert_called_once()
        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer mock_token_123"

@pytest.mark.asyncio
async def test_token_loaded_from_token_enc():
    """Verify that the token is actually loaded from token.enc via TokenStore."""
    import os
    import base64
    os.environ["TOKEN_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()
    auth_manager = AuthManager()
    
    with patch("auth.token_store.TokenStore.get_token_payload") as mock_get_payload:
        mock_get_payload.return_value = {"access_token": "token_from_enc"}
        
        # Override is_token_valid to true for testing
        with patch.object(auth_manager, 'is_token_valid', return_value=True):
            token = auth_manager.get_access_token()
            assert token == "token_from_enc"
            mock_get_payload.assert_called_once()

@pytest.mark.asyncio
async def test_ws_auth_401_retry():
    """Verify that a 401 response triggers a silent refresh and retry."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_access_token.side_effect = ["old_token", "new_token"]
    mock_auth_manager.silent_refresh = AsyncMock(return_value=True)
    
    mock_meta = MagicMock()
    mock_meta.created_at = 1000
    mock_meta.expires_at = 2000
    mock_auth_manager.store.get_token_meta.return_value = mock_meta
    
    ws_client = UpstoxWSClient(mock_auth_manager)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # First call returns 401, second returns 200
        mock_401 = MagicMock()
        mock_401.status_code = 401
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": {"authorized_redirect_uri": "wss://test.upstox.com"}}
        
        mock_get.side_effect = [mock_401, mock_200]
        
        uri = await ws_client._get_ws_uri()
        
        assert uri == "wss://test.upstox.com"
        assert mock_get.call_count == 2
        mock_auth_manager.silent_refresh.assert_called_once()
        
        # Check that the second call used the new token
        headers_second_call = mock_get.call_args_list[1][1]["headers"]
        assert headers_second_call["Authorization"] == "Bearer new_token"
