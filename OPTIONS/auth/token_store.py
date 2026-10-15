import os
import json
import time
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger
from typing import Optional, Dict
from dotenv import load_dotenv
load_dotenv()

from auth.schema import TokenMeta, TokenState

CONFIG_DIR = Path("config")
TOKEN_ENC_PATH = CONFIG_DIR / "token.enc"
TOKEN_META_PATH = CONFIG_DIR / "token_meta.json"

class TokenStore:
    def __init__(self):
        encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("TOKEN_ENCRYPTION_KEY environment variable is missing")
        self._fernet = Fernet(encryption_key.strip().encode())
        CONFIG_DIR.mkdir(exist_ok=True)

    def save_token(self, token_data: Dict[str, str], meta: TokenMeta):
        """Save encrypted token payload and cleartext metadata."""
        try:
            # Encrypt token payload (access_token, refresh_token, etc.)
            payload = json.dumps(token_data).encode()
            encrypted_payload = self._fernet.encrypt(payload)
            
            TOKEN_ENC_PATH.write_bytes(encrypted_payload)
            
            # Save metadata
            with open(TOKEN_META_PATH, "w") as f:
                f.write(meta.model_dump_json(indent=2))
                
            logger.info("Token and metadata successfully saved locally")
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            raise

    def _get_fallback_payload(self) -> Optional[Dict[str, str]]:
        env_token = os.getenv("UPSTOX_ACCESS_TOKEN")
        if env_token:
            return {"access_token": env_token}
        web_token_path = Path(__file__).resolve().parent.parent.parent / "stock webpage - Copy" / "server" / "data" / "upstox_token.json"
        if web_token_path.exists():
            try:
                data = json.loads(web_token_path.read_text(encoding="utf-8"))
                if data.get("access_token"):
                    return data
            except Exception:
                pass
        return None

    def get_token_payload(self) -> Optional[Dict[str, str]]:
        """Retrieve and decrypt the token payload, falling back to web token store or env."""
        fallback = self._get_fallback_payload()
        web_token_path = Path(__file__).resolve().parent.parent.parent / "stock webpage - Copy" / "server" / "data" / "upstox_token.json"
        
        # If web token exists and is newer than token.enc, or token.enc is missing, sync immediately!
        should_sync_web = False
        if web_token_path.exists() and fallback:
            if not TOKEN_ENC_PATH.exists():
                should_sync_web = True
            else:
                try:
                    if web_token_path.stat().st_mtime > TOKEN_ENC_PATH.stat().st_mtime:
                        should_sync_web = True
                except Exception:
                    pass

        if should_sync_web and fallback:
            try:
                meta = TokenMeta(
                    state=TokenState.VALID,
                    created_at=time.time(),
                    expires_at=time.time() + 86400
                )
                self.save_token(fallback, meta)
                logger.info("Successfully synced fresh web token into encrypted token store.")
                return fallback
            except Exception as err:
                logger.warning(f"Could not re-persist fallback token: {err}")

        if TOKEN_ENC_PATH.exists():
            try:
                encrypted_payload = TOKEN_ENC_PATH.read_bytes()
                decrypted_payload = self._fernet.decrypt(encrypted_payload)
                return json.loads(decrypted_payload.decode())
            except Exception as e:
                logger.warning(f"Could not decrypt local token.enc (key changed): {e}. Attempting fallback...")
        
        if fallback:
            try:
                meta = TokenMeta(
                    state=TokenState.VALID,
                    created_at=time.time(),
                    expires_at=time.time() + 86400
                )
                self.save_token(fallback, meta)
                logger.info("Successfully synced fallback token into encrypted token store.")
            except Exception as err:
                logger.warning(f"Could not re-persist fallback token: {err}")
        return fallback

    def get_token_meta(self) -> Optional[TokenMeta]:
        """Retrieve the token metadata, generating fallback meta if cleartext token exists."""
        if TOKEN_META_PATH.exists():
            try:
                with open(TOKEN_META_PATH, "r") as f:
                    data = json.load(f)
                meta = TokenMeta(**data)
                if meta.state == TokenState.VALID:
                    return meta
            except Exception as e:
                logger.warning(f"Could not parse token metadata: {e}")
                
        payload = self.get_token_payload()
        if payload and payload.get("access_token"):
            return TokenMeta(
                state=TokenState.VALID,
                created_at=time.time(),
                expires_at=time.time() + 86400
            )
        return None


    def update_meta_state(self, state: TokenState):
        """Update just the token state in metadata."""
        meta = self.get_token_meta()
        if meta:
            meta.state = state
            with open(TOKEN_META_PATH, "w") as f:
                f.write(meta.model_dump_json(indent=2))
            logger.debug(f"Token state updated to {state.value}")
