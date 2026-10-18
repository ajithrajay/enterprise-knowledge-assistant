"""FastAPI application entry-point."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers import auth, chat, tickets, ingest, analytics

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s")

SEED = [
    ("HR-LEAVE-v3", "Leave Policy", "v3", "intern",
     "Full-time employees receive 18 paid leave days per year. "
     "Interns receive 1 leave day per month. Unused leave up to 10 days carries over. "
     "Leave requests over 5 consecutive days need manager approval."),
    ("FIN-TRAVEL-v2", "Travel Reimbursement", "v2", "employee",
     "Domestic travel hotel reimbursement is capped at Rs 6,000 per night. "
     "International travel needs prior approval from the department head. "
     "Claims must be filed within 30 days with original receipts."),
    ("PROC-VENDOR-v4", "Vendor Contract Approval", "v4", "employee",
     "Vendor contracts up to Rs 5 lakh are approved by the department manager. "
     "Contracts above Rs 5 lakh need finance head approval. "
     "Contracts above Rs 25 lakh need CFO sign-off."),
    ("IT-LAPTOP-v1", "Laptop and Hardware Policy", "v1", "employee",
     "Contractor laptop purchases at the Chennai office are approved by the site IT lead, "
     "with a budget limit of Rs 75,000 per device. Lost devices must be reported within 24 hours."),
    ("HR-SALARY-v2", "Salary Bands Confidential", "v2", "hr_admin",
     "Band L3 salary range is Rs 12 to 18 lakh per year. "
     "Band L4 salary range is Rs 18 to 28 lakh per year. Restricted to HR administrators."),
    ("MGR-APPRAISAL-v1", "Appraisal Guidelines", "v1", "manager",
     "Managers must complete appraisal reviews within 14 days of cycle closing. "
     "Rating distribution must follow HR calibration guidelines."),
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.ingestion import ingest_text
    from app.services.vector_store import collection_size
    if collection_size() == 0:
        for doc_id, title, version, min_role, text in SEED:
            ingest_text(doc_id, title, version, min_role, text)
    from app.services.vector_store import set_min_score
    set_min_score(0.20)
    yield

app = FastAPI(title="Enterprise Knowledge Assistant", version="2.0.0", lifespan=lifespan)

for router in [auth.router, chat.router, tickets.router, ingest.router, analytics.router]:
    app.include_router(router)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health():
    from app.services.vector_store import collection_size
    return {"ok": True, "docs_indexed": collection_size()}

@app.get("/", include_in_schema=False)
def index(): return FileResponse("static/index.html")
