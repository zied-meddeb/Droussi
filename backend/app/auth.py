from fastapi import HTTPException, Request, status
from pydantic import BaseModel
import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
import httpx
import json

from .config import get_settings

_jwks_cache: list[dict] = []


class CurrentUser(BaseModel):
    id: str
    email: str | None = None


def _load_jwks(force: bool = False) -> list[dict]:
    global _jwks_cache
    if _jwks_cache and not force:
        return _jwks_cache
    url = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json().get("keys", [])
    return _jwks_cache


def _public_key_for(kid: str | None, alg: str):
    for attempt in (False, True):  # second pass forces a JWKS refresh
        keys = _load_jwks(force=attempt)
        key_data = next((k for k in keys if not kid or k.get("kid") == kid), keys[0] if keys else None)
        if key_data:
            raw = json.dumps(key_data)
            if alg.startswith("ES"):
                return ECAlgorithm.from_jwk(raw)
            if alg.startswith("RS"):
                return RSAAlgorithm.from_jwk(raw)
    raise ValueError(f"No matching public key found in JWKS for kid={kid}")


def get_current_user(request: Request) -> CurrentUser:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = auth.removeprefix("Bearer ").strip()
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "ES256")
        kid = header.get("kid")
        public_key = _public_key_for(kid, alg)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("No sub claim in token")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e
    return CurrentUser(id=user_id, email=payload.get("email"))
