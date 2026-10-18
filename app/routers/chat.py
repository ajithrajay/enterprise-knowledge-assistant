from fastapi import APIRouter, Depends
from app.models.schemas import ChatIn, ChatOut
from app.services.auth import get_current_user
from app.services.pipeline import run

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user=Depends(get_current_user)):
    result = run(body.query, user["role"], user["username"])
    return ChatOut(**{k: v for k, v in result.items() if k != "from_cache"})
