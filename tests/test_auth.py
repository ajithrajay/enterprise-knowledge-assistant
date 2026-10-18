from tests.conftest import auth
from app.services.auth import verify, create_token
from jose import jwt
from app.config import get_settings

def test_verify_good():
    assert verify("alice", "alice123") is not None

def test_verify_bad():
    assert verify("alice", "wrong") is None

def test_token_round_trip():
    tok = create_token("alice", "employee")
    cfg = get_settings()
    payload = jwt.decode(tok, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
    assert payload["sub"] == "alice" and payload["role"] == "employee"
