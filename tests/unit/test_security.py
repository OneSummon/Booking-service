import hashlib
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt

from app.config import settings
from app.schemas.enums import UserStatus
from app.security import (
    create_access_token,
    get_real_ip,
    hash_obj,
    hash_token,
    verify,
    verify_user_is_admin,
)


class TestHashObj:
    def test_returns_string(self):
        assert isinstance(hash_obj("mypassword"), str)

    def test_bcrypt_uses_random_salt(self):
        h1 = hash_obj("mypassword")
        h2 = hash_obj("mypassword")
        assert h1 != h2

    def test_result_is_non_empty(self):
        assert len(hash_obj("x")) > 0


class TestVerify:
    def test_correct_password(self):
        h = hash_obj("secret123")
        assert verify("secret123", h) is True

    def test_wrong_password(self):
        h = hash_obj("secret123")
        assert verify("wrong", h) is False

    def test_empty_against_hash(self):
        h = hash_obj("something")
        assert verify("", h) is False


class TestHashToken:
    def test_deterministic(self):
        assert hash_token("abc") == hash_token("abc")

    def test_matches_sha256(self):
        expected = hashlib.sha256("mytoken".encode()).hexdigest()
        assert hash_token("mytoken") == expected

    def test_different_inputs_differ(self):
        assert hash_token("token1") != hash_token("token2")

    def test_returns_hex_string(self):
        result = hash_token("x")
        assert all(c in "0123456789abcdef" for c in result)


class TestCreateAccessToken:
    def test_is_string(self):
        assert isinstance(create_access_token({"sub": "1"}), str)

    def test_decodable_with_correct_key(self):
        token = create_access_token({"sub": "42", "role": "user"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == "42"
        assert payload["role"] == "user"

    def test_contains_expiry(self):
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert "exp" in payload

    def test_custom_claims_preserved(self):
        token = create_access_token({"sub": "99", "role": "admin", "extra": "value"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["extra"] == "value"


class TestGetRealIp:
    def test_prefers_x_real_ip_header(self):
        request = MagicMock()
        request.headers.get.return_value = "1.2.3.4"
        assert get_real_ip(request) == "1.2.3.4"

    def test_falls_back_to_client_host(self):
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "5.6.7.8"
        assert get_real_ip(request) == "5.6.7.8"

    def test_returns_unknown_when_no_client(self):
        request = MagicMock()
        request.headers.get.return_value = None
        request.client = None
        assert get_real_ip(request) == "unknown"


class TestVerifyUserIsAdmin:
    def test_passes_for_admin(self):
        verify_user_is_admin(UserStatus.admin)

    def test_raises_403_for_regular_user(self):
        with pytest.raises(HTTPException) as exc:
            verify_user_is_admin(UserStatus.user)
        assert exc.value.status_code == 403
