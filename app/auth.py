import os
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm

# Simple secret token based auth (fallback if JWT libs unavailable)
SECRET_KEY = os.getenv("API_TOKEN", "default-token")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

bearer_scheme = HTTPBearer(auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a simple token. For demo purposes we return the secret key itself.
    In a production setting you would encode a JWT using a library like python‑jose.
    """
    # Very naive token – just the secret prefixed with a timestamp (not secure)
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = data.copy()
    payload.update({"exp": int(expire.timestamp())})
    token_str = f"{SECRET_KEY}:{payload.get('sub', '')}:{int(time.time())}"
    return token_str

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")
    token = credentials.credentials
    # Very simple validation – token must start with the secret key
    if not token.startswith(SECRET_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # Return a dummy user dict
    return {"sub": "admin"}

# The login endpoint (already defined in main) uses this module's create_access_token.
