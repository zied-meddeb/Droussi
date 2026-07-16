import json
import logging
import time

from fastapi import HTTPException, Request, status
from pydantic import BaseModel
import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
import httpx

from .config import get_settings

logger = logging.getLogger(__name__)

# Cache the JWKS but refresh it periodically so Supabase key rotation is picked
# up without a restart. A kid miss still forces an immediate refresh (see
# _public_key_and_alg).
_JWKS_TTL_SECONDS = 3600
_jwks_cache: list[dict] = []
_jwks_fetched_at: float = 0.0


class CurrentUser(BaseModel):
    id: str
    email: str | None = None


def _load_jwks(force: bool = False) -> list[dict]:
    global _jwks_cache, _jwks_fetched_at
    is_fresh = (time.monotonic() - _jwks_fetched_at) < _JWKS_TTL_SECONDS
    if _jwks_cache and is_fresh and not force:
        return _jwks_cache
    url = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json().get("keys", [])
    _jwks_fetched_at = time.monotonic()
    return _jwks_cache


# Signing algorithms we accept. Derived from the JWKS (a trusted source) rather
# than from the token header, so a forged "alg" claim cannot trigger an
# algorithm-confusion attack.
_ALLOWED_ALGS = ("ES256", "RS256")


def _public_key_and_alg(kid: str | None):
    """Return (public_key, alg) for the given key id, using the algorithm the
    JWKS itself advertises — never the (untrusted) token header."""
    for attempt in (False, True):  # second pass forces a JWKS refresh
        keys = _load_jwks(force=attempt)
        key_data = next((k for k in keys if not kid or k.get("kid") == kid), keys[0] if keys else None)
        if key_data:
            alg = key_data.get("alg", "ES256")
            if alg not in _ALLOWED_ALGS:
                continue
            raw = json.dumps(key_data)
            if alg.startswith("ES"):
                return ECAlgorithm.from_jwk(raw), alg
            if alg.startswith("RS"):
                return RSAAlgorithm.from_jwk(raw), alg
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
        # The header is only used to select the signing key (kid). The algorithm
        # and signature are verified below against the trusted JWKS key.
        kid = jwt.get_unverified_header(token).get("kid")
        public_key, alg = _public_key_and_alg(kid)
        settings = get_settings()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            audience=settings.supabase_jwt_aud,
            issuer=settings.supabase_jwt_issuer,
            options={"verify_aud": True, "verify_iss": True, "require": ["exp"]},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("No sub claim in token")
    except Exception as e:
        # Log the underlying reason server-side; never leak it to the client.
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from e
    return CurrentUser(id=user_id, email=payload.get("email"))
