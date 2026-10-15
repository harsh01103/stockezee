import os
import json
import time
import socket
import webbrowser
import urllib.parse
# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from loguru import logger
from typing import Optional
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

from auth.schema import UpstoxCredentials, TokenMeta, TokenState
from auth.token_store import TokenStore
from auth.upstox_auth import UpstoxAuthClient

class AuthManager:
    def __init__(self):
        self.store = TokenStore()
        
        # Load from environment
        api_key = os.getenv("UPSTOX_API_KEY")
        api_secret = os.getenv("UPSTOX_API_SECRET")
        redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8787")
        
        if not api_key or not api_secret:
            logger.warning("Upstox credentials missing from environment variables")
            
        self.credentials = UpstoxCredentials(
            api_key=api_key or "",
            api_secret=api_secret or "",
            redirect_uri=redirect_uri
        )
        self.client = UpstoxAuthClient(self.credentials)
        logger.info("Initializing AuthManager")

    async def ensure_valid_token(self, interactive_allowed: bool = True) -> Optional[str]:
        """Ensures a valid token exists, fetching or refreshing if necessary."""
        token_meta = self.store.get_token_meta()
        
        if token_meta and token_meta.state == TokenState.VALID:
            # Check if close to expiry (e.g. less than 1 hour)
            if token_meta.expires_at < time.time() + 3600:
                logger.info("Token nearing expiry, attempting silent refresh.")
                success = await self.silent_refresh()
                if not success and interactive_allowed:
                    await self.interactive_login()
            else:
                return self.get_access_token()
                
        elif token_meta and token_meta.state == TokenState.REFRESHING:
            logger.warning("Token refresh currently in progress by another process.")
            return None
            
        else:
            if interactive_allowed:
                await self.interactive_login()
            else:
                logger.error("Token invalid and interactive login not allowed.")
                return None
            
        return self.get_access_token()

    def is_token_valid(self) -> bool:
        """Check if we have a valid token that is not expired."""
        meta = self.store.get_token_meta()
        if not meta or meta.state != TokenState.VALID:
            return False
            
        # Check if expired (Upstox tokens usually valid for 24h)
        # Adding a 5 min buffer
        if time.time() > (meta.expires_at - 300):
            return False
            
        return True

    def get_access_token(self) -> Optional[str]:
        """Get the cleartext access token if valid."""
        if not self.is_token_valid():
            return None
        payload = self.store.get_token_payload()
        if payload:
            if isinstance(payload, dict):
                return payload.get("access_token")
            # Handle JSON string payload
            try:
                return json.loads(payload).get("access_token")
            except:
                return None
        return None

    async def validate_token_rest(self) -> bool:
        """Validates the token against the Upstox REST API."""
        token = self.get_access_token()
        if not token:
            return False
            
        url = "https://api.upstox.com/v2/user/profile"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 401:
                    logger.warning("Token validation failed with 401 Unauthorized.")
                    self.store.update_meta_state(TokenState.EXPIRED)
                    return False
                response.raise_for_status()
                logger.info("Token validated successfully via REST API.")
                return True
        except Exception as e:
            logger.error(f"Error validating token via REST: {e}")
            return False

    def _capture_auth_code_local(self, port: int) -> str:
        """Starts a temporary local server to capture the redirect code."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(900.0) # 15 minute timeout
            s.bind(('localhost', port))
            s.listen(1)
            logger.info(f"Waiting for authorization callback on localhost:{port} (15m timeout)...")
            
            while True:
                try:
                    conn, addr = s.accept()
                except socket.timeout:
                    logger.error("Authorization callback timed out after 15 minutes.")
                    raise TimeoutError("Auth timeout")
                    
                with conn:
                    request_data = conn.recv(4096).decode('utf-8')
                    if not request_data:
                        continue
                        
                    response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html><body><h1>Authorization Successful</h1><p>You can close this window and return to the terminal.</p></body></html>"
                    conn.sendall(response.encode('utf-8'))
                    
                    try:
                        first_line = request_data.split('\r\n')[0]
                        parts = first_line.split(' ')
                        if len(parts) < 2:
                            continue
                        path = parts[1]
                        query = urllib.parse.urlparse(path).query
                        params = urllib.parse.parse_qs(query)
                        code = params.get('code', [None])[0]
                        if code:
                            return code
                    except Exception as e:
                        logger.error(f"Failed to parse authorization code from callback: {e}")
                        continue

    async def interactive_login(self):
        """Perform the interactive browser-based login flow."""
        port = urllib.parse.urlparse(self.credentials.redirect_uri).port or 8787
        
        login_url = self.client.get_login_url()
        logger.info(f"Opening browser for login: {login_url}")
        
        # Open browser
        webbrowser.open(login_url)
        
        # Start local listener and block until we get the code
        try:
            code = self._capture_auth_code_local(port)
            logger.info(f"Captured auth code: {code[:5]}...")
            
            # Exchange for token
            auth_data = await self.client.get_token_from_code(code)
            
            # Save token
            expires_in = auth_data.get('expires_in', 86400)
            
            meta = TokenMeta(
                state=TokenState.VALID,
                created_at=time.time(),
                expires_at=time.time() + float(expires_in)
            )
            
            # Construct payload
            payload = json.dumps({
                "access_token": auth_data["access_token"],
                "refresh_token": auth_data.get("refresh_token", "")
            })
            
            self.store.save_token(payload, meta)
            logger.info("Authentication successful.")
            
        except Exception as e:
            logger.error(f"Interactive login failed: {e}")
            self.store.update_meta_state(TokenState.FAILED)
            raise

    async def silent_refresh(self) -> bool:
        """Attempts to silently refresh the token."""
        try:
            self.store.update_meta_state(TokenState.REFRESHING)
            token_payload = self.store.get_token_payload()
            if not token_payload:
                return False
                
            try:
                data = json.loads(token_payload) if isinstance(token_payload, str) else token_payload
                refresh_token = data.get("refresh_token")
            except:
                refresh_token = None
                
            if not refresh_token:
                logger.warning("No refresh token available for silent refresh.")
                self.store.update_meta_state(TokenState.EXPIRED)
                return False
                
            auth_data = await self.client.refresh_access_token(refresh_token)
            
            payload = json.dumps({
                "access_token": auth_data["access_token"],
                "refresh_token": auth_data.get("refresh_token", refresh_token)
            })
            
            meta = TokenMeta(
                state=TokenState.VALID,
                created_at=time.time(),
                expires_at=time.time() + float(auth_data["expires_in"])
            )
            
            self.store.save_token(payload, meta)
            logger.info("Silent token refresh successful.")
            return True
        except Exception as e:
            logger.error(f"Silent refresh failed: {e}")
            self.store.update_meta_state(TokenState.EXPIRED)
            return False
