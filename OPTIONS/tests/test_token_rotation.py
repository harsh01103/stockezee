import pytest
import time
from auth.auth_manager import AuthManager
from auth.schema import TokenState, TokenMeta
from auth.token_store import TokenStore

def test_token_expiry_detection(monkeypatch, tmp_path):
    import auth.token_store
    auth.token_store.CONFIG_DIR = tmp_path
    auth.token_store.TOKEN_ENC_PATH = tmp_path / "token.enc"
    auth.token_store.TOKEN_META_PATH = tmp_path / "token_meta.json"
    
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "uO1XzQv6-W5m0xH2YtL1m0xH2YtL1m0xH2YtL_12345=")
    
    manager = AuthManager()
    
    # Simulate expired token
    meta = TokenMeta(state=TokenState.VALID, created_at=time.time() - 86400, expires_at=time.time() - 100)
    manager.store.save_token({"access_token": "expired"}, meta)
    
    assert manager.is_token_valid() is False

    # Simulate valid token
    meta = TokenMeta(state=TokenState.VALID, created_at=time.time(), expires_at=time.time() + 86400)
    manager.store.save_token({"access_token": "valid"}, meta)
    
    assert manager.is_token_valid() is True
