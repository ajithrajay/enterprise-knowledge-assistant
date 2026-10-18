import pytest
from fastapi.testclient import TestClient
from app.main import app, SEED
from app.services.auth import create_token
from app.services import vector_store as _vs

@pytest.fixture(scope="session", autouse=True)
def seed_docs():
    from app.services.ingestion import ingest_text
    _vs.set_min_score(0.20)
    if _vs.collection_size() == 0:
        for doc_id, title, version, min_role, text in SEED:
            ingest_text(doc_id, title, version, min_role, text)

@pytest.fixture(scope="session")
def client(seed_docs):
    with TestClient(app) as c:
        yield c

def auth(role: str) -> dict:
    token = create_token(role, role)
    return {"Authorization": f"Bearer {token}"}
