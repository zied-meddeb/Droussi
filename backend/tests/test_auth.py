"""Tests for JWT authentication, including a real ES256-signed token."""
import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jwt.algorithms import ECAlgorithm

from app import auth
from app.auth import get_current_user


class FakeRequest:
    def __init__(self, headers):
        self.headers = headers


def _make_key_and_jwk(kid="test-kid"):
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    jwk["alg"] = "ES256"
    jwk["kid"] = kid
    return private_key, jwk


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
            {"sub": "user123", "email": "user@test.com"},
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
        token = jwt.encode(
            {"email": "user@test.com"}, private_key, algorithm="ES256", headers={"kid": "test-kid"}
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401

    def test_no_keys_in_jwks_is_rejected(self, monkeypatch):
        private_key, _ = _make_key_and_jwk()
        monkeypatch.setattr(auth, "_load_jwks", lambda force=False: [])
        token = jwt.encode({"sub": "user123"}, private_key, algorithm="ES256")
        with pytest.raises(HTTPException) as exc:
            get_current_user(FakeRequest({"Authorization": f"Bearer {token}"}))
        assert exc.value.status_code == 401
