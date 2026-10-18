"""JWT auth + hashed user store. Replace with SSO/LDAP in production."""
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import get_settings
from app.models.schemas import RoleLevel

pwd = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Pre-hashed passwords (sha256_crypt, no bcrypt length issues)
_USERS: dict[str, dict] = {
    "alice":  {"password": pwd.hash("alice123"),  "role": "employee"},
    "bob":    {"password": pwd.hash("bob456"),    "role": "manager"},
    "carol":  {"password": pwd.hash("carol789"),  "role": "hr_admin"},
    "dave":   {"password": pwd.hash("dave000"),   "role": "intern"},
}

def verify(username: str, password: str) -> dict | None:
    u = _USERS.get(username)
    return u if u and pwd.verify(password, u["password"]) else None

def create_token(username: str, role: str) -> str:
    cfg = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=cfg.jwt_expire_minutes)
    return jwt.encode({"sub": username, "role": role, "exp": exp},
                      cfg.jwt_secret, cfg.jwt_algorithm)

def get_current_user(token: str = Depends(oauth2)) -> dict:
    cfg = get_settings()
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
        return {"username": payload["sub"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})

def require_role(min_role: str):
    def dep(user=Depends(get_current_user)):
        if RoleLevel[user["role"]] < RoleLevel[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return dep
