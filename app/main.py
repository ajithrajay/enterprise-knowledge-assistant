"""FastAPI application entry-point — Nexova Technologies knowledge base."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.seed_data import COMPANY_DOCS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s"
)

# keep SEED exported so tests can import it
SEED = [(d["id"], d["title"], d["version"], d["min_role"], d["text"])
        for d in COMPANY_DOCS]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.ingestion import ingest_text
    from app.services.vector_store import collection_size, set_min_score

    # set_min_score(0.38)

    if collection_size() == 0:
        logging.info("Seeding Nexova knowledge base (%d documents)…", len(COMPANY_DOCS))
        for doc in COMPANY_DOCS:
            ingest_text(doc["id"], doc["title"], doc["version"],
                        doc["min_role"], doc["text"])
        logging.info("Knowledge base ready — %d chunks indexed.", collection_size())
    yield


from app.routers import auth, chat, tickets, ingest, analytics

app = FastAPI(
    title="Nexova Enterprise Knowledge Assistant",
    version="2.0.0",
    lifespan=lifespan,
)

for router in [auth.router, chat.router, tickets.router,
               ingest.router, analytics.router]:
    app.include_router(router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health():
    from app.services.vector_store import collection_size
    return {"ok": True, "company": "Nexova Technologies",
            "docs_indexed": collection_size()}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")
