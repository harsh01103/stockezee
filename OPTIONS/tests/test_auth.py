import pytest
import os
import time
from cryptography.fernet import Fernet
from auth.token_store import TokenStore
from auth.schema import TokenMeta, TokenState

def test_token_encryption(tmp_path, monkeypatch):
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", test_key)
    
    # Override paths
    import auth.token_store
    auth.token_store.CONFIG_DIR = tmp_path
    auth.token_store.TOKEN_ENC_PATH = tmp_path / "token.enc"
    auth.token_store.TOKEN_META_PATH = tmp_path / "token_meta.json"
    
    store = TokenStore()
    
    token_data = {"access_token": "secret_token_123"}
    meta = TokenMeta(state=TokenState.VALID, created_at=time.time(), expires_at=time.time() + 3600)
    
    store.save_token(token_data, meta)
    
    assert auth.token_store.TOKEN_ENC_PATH.exists()
    assert auth.token_store.TOKEN_META_PATH.exists()
    
    # Raw file should not contain cleartext
    raw_enc = auth.token_store.TOKEN_ENC_PATH.read_bytes()
    assert b"secret_token_123" not in raw_enc
    
    # Decryption should work
    payload = store.get_token_payload()
    assert payload["access_token"] == "secret_token_123"
    
    # State update
    store.update_meta_state(TokenState.EXPIRED)
    new_meta = store.get_token_meta()
    assert new_meta.state == TokenState.EXPIRED
