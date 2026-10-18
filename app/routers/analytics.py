import json
from collections import Counter
from pathlib import Path
from fastapi import APIRouter, Depends
from app.services.auth import require_role
from app.services.vector_store import collection_size
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["analytics"])

@router.get("/analytics")
def analytics(user=Depends(require_role("manager"))):
    p = Path(get_settings().audit_path)
    events = [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
    asked   = sum(1 for e in events if e["event"] in ("answered","refused"))
    answered= sum(1 for e in events if e["event"] == "answered")
    refused = sum(1 for e in events if e["event"] == "refused")
    tickets = sum(1 for e in events if e["event"] == "ticket_created")
    unanswered = [e.get("query","") for e in events if e["event"] == "refused"]
    latencies = [e["ms"] for e in events if "ms" in e]
    common = Counter(unanswered).most_common(10)
    return {"asked": asked, "answered": answered, "refused": refused, "tickets": tickets,
            "top_unanswered": [{"q": q, "count": c} for q, c in common],
            "p50_ms": sorted(latencies)[len(latencies)//2] if latencies else 0,
            "p95_ms": sorted(latencies)[int(len(latencies)*.95)] if latencies else 0,
            "collection_size": collection_size()}
