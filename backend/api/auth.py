"""
api/auth.py — JWT authentication
Single-user login. Credentials stored in .env.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt as _bcrypt
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/api/auth")
bearer = HTTPBearer(auto_error=False)

_ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _make_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode(
        {"sub": username, "exp": expire},
        settings.jwt_secret,
        algorithm=_ALGORITHM,
    )


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> str:
    """Dependency — raises 401 if token missing or invalid."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret,
                             algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise ValueError
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")
    return username


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Exchange username+password for a JWT."""
    ok = (
        body.username == settings.trading_username
        and bool(settings.trading_password_hash)
        and _bcrypt.checkpw(
            body.password.encode(),
            settings.trading_password_hash.encode(),
        )
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid credentials")
    return TokenResponse(access_token=_make_token(body.username))


@router.get("/me")
async def me(username: str = Depends(verify_token)):
    """Return logged-in username (used by frontend to validate token)."""
    return {"username": username}
