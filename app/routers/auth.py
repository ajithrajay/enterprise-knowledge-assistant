from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.services.auth import verify, create_token
from app.models.schemas import Token

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = verify(form.username, form.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    token = create_token(form.username, user["role"])
    return Token(access_token=token, role=user["role"], username=form.username)
