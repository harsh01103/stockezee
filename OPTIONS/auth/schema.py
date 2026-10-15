from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TokenState(str, Enum):
    VALID = "VALID"
    REFRESHING = "REFRESHING"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"

class TokenMeta(BaseModel):
    state: TokenState
    created_at: float
    expires_at: float

class UpstoxCredentials(BaseModel):
    api_key: str
    api_secret: str
    redirect_uri: str
