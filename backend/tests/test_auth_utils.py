from datetime import timedelta

from app.utils.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)


def test_verify_wrong_password():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_create_and_decode_token():
    data = {"sub": "42", "role": "admin"}
    token = create_access_token(data)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"


def test_decode_expired_token():
    data = {"sub": "42", "role": "admin"}
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    payload = decode_access_token(token)
    assert payload is None


def test_decode_invalid_token():
    payload = decode_access_token("not.a.valid.token")
    assert payload is None
