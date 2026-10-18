from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.models.schemas import IngestIn
from app.services.auth import require_role
from app.services.ingestion import ingest_text, ingest_pdf
from app.services import audit

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/ingest/text")
def ingest_text_route(body: IngestIn, user=Depends(require_role("hr_admin"))):
    n = ingest_text(body.title.upper().replace(" ","-")+"-"+body.version,
                    body.title, body.version, body.min_role, body.text)
    doc_id = body.title.upper().replace(" ","-")+"-"+body.version
    audit.write("ingested", doc_id=doc_id, chunks=n, user=user["username"])
    return {"doc_id": doc_id, "chunks": n}

@router.post("/ingest/pdf")
async def ingest_pdf_route(
    title: str = Form(...), version: str = Form(...),
    min_role: str = Form("employee"),
    file: UploadFile = File(...),
    user=Depends(require_role("hr_admin"))):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")
    pdf_bytes = await file.read()
    doc_id = title.upper().replace(" ","-")+"-"+version
    n = ingest_pdf(doc_id, title, version, min_role, pdf_bytes)
    audit.write("ingested_pdf", doc_id=doc_id, chunks=n, user=user["username"])
    return {"doc_id": doc_id, "chunks": n}
