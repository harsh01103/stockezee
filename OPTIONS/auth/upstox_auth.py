import urllib.parse
import httpx
from loguru import logger
from typing import Dict, Any

from auth.schema import UpstoxCredentials

class UpstoxAuthClient:
    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self, credentials: UpstoxCredentials):
        self.credentials = credentials

    def get_login_url(self) -> str:
        """Generate the authorization URL for user login."""
        params = {
            "response_type": "code",
            "client_id": self.credentials.api_key,
            "redirect_uri": self.credentials.redirect_uri
        }
        query_string = urllib.parse.urlencode(params)
        return f"{self.BASE_URL}/login/authorization/dialog?{query_string}"

    async def get_token_from_code(self, code: str) -> Dict[str, Any]:
        """Exchange the authorization code for an access token."""
        url = f"{self.BASE_URL}/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "code": code,
            "client_id": self.credentials.api_key,
            "client_secret": self.credentials.api_secret,
            "redirect_uri": self.credentials.redirect_uri,
            "grant_type": "authorization_code"
        }

        logger.info("Exchanging auth code for access token...")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            
            if response.status_code != 200:
                logger.error(f"Failed to get token: {response.text}")
                response.raise_for_status()

            return response.json()
