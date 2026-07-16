"""Tests for JWT authentication, including a real ES256-signed token."""
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jwt.algorithms import ECAlgorithm

from app import auth
from app.auth import get_current_user

# Must match conftest's SUPABASE_URL / expected audience.
TEST_ISS = "https://test.supabase.co/auth/v1"
TEST_AUD = "authenticated"


class FakeRequest:
    def __init__(self, headers):
        self.headers = headers


def _make_key_and_jwk(kid="test-kid"):
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    jwk["alg"] = "ES256"
    jwk["kid"] = kid
    return private_key, jwk


def _claims(**over):
    """Base claims for a valid Supabase user token (aud/iss/exp present)."""
    base = {
        "sub": "user123",
        "email": "user@test.com",
        "aud": TEST_AUD,
        "iss": TEST_ISS,
        "exp": int(time.time()) + 3600,
    }
    base.update(over)
    return base


class TestMissingOrBadToken:
    def test_missing_authorization_header(self):
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({}))
        assert exc.value.status_code == 401

    def test_non_bearer_scheme(self):
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": "Basic abc"}))
        assert exc.value.status_code == 401

    def test_garbage_token(self):
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": "Bearer not-a-jwt"}))
        assert exc.value.status_code == 401


class TestValidToken:
    def test_valid_token_returns_user(self, monkeypatch):
        private_key, jwk = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [jwk])
        token = jwt.encode(
            _claims(),
            private_key,
            algorithm="ES256",
            headers={"kid": "test-kid"},
        )
        user = get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert user.id == "user123"
        assert user.email == "user@test.com"

    def test_token_without_sub_is_rejected(self, monkeypatch):
        private_key, jwk = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [jwk])
        claims = _claims()
        claims.pop("sub")
        token = jwt.encode(
            claims, private_key, algorithm="ES256", headers={"kid": "test-kid"}
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401

    def test_wrong_audience_is_rejected(self, monkeypatch):
        private_key, jwk = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [jwk])
        token = jwt.encode(
            _claims(aud="some-other-service"),
            private_key,
            algorithm="ES256",
            headers={"kid": "test-kid"},
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401

    def test_wrong_issuer_is_rejected(self, monkeypatch):
        private_key, jwk = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [jwk])
        token = jwt.encode(
            _claims(iss="https://evil.example/auth/v1"),
            private_key,
            algorithm="ES256",
            headers={"kid": "test-kid"},
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401

    def test_expired_token_is_rejected(self, monkeypatch):
        private_key, jwk = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [jwk])
        token = jwt.encode(
            _claims(exp=int(time.time()) - 10),
            private_key,
            algorithm="ES256",
            headers={"kid": "test-kid"},
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401

    def test_no_keys_in_jwks_is_rejected(self, monkeypatch):
        private_key, _ = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [])
        token = jwt.encode(_claims(), private_key, algorithm="ES256")
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401
