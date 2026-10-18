import uuid
from fastapi import APIRouter, Depends
from app.models.schemas import TicketIn, TicketOut
from app.services.auth import get_current_user
from app.services import audit

router = APIRouter(prefix="/api", tags=["tickets"])

@router.post("/ticket", response_model=TicketOut)
def ticket(body: TicketIn, user=Depends(get_current_user)):
    if not body.confirmed:
        return TicketOut(status="needs_confirmation",
                         message=f"Raise ticket: '{body.summary}'? Confirm to proceed.")
    tid = f"IT-{uuid.uuid4().hex[:6].upper()}"
    audit.write("ticket_created", ticket=tid, role=user["role"],
                user=user["username"], summary=body.summary)
    return TicketOut(status="created", ticket_id=tid,
                     message=f"Ticket {tid} raised. HR/IT will contact you within 24 hours.")
