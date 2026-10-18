"""Qdrant vector store with RBAC metadata filtering.
Falls back to in-memory TF-IDF when Qdrant is unreachable (offline dev)."""
import uuid, logging
from functools import lru_cache
from app.config import get_settings
from app.models.schemas import RoleLevel

log = logging.getLogger(__name__)
DIM = 384   # all-MiniLM-L6-v2 dimension

# ── try Qdrant ─────────────────────────────────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchAny, ScoredPoint
    )
    _QDRANT_OK = True
except ImportError:
    _QDRANT_OK = False

@lru_cache(maxsize=1)
def _client():
    cfg = get_settings()
    c = QdrantClient(url=cfg.qdrant_url, timeout=5)
    # create collection if it doesn't exist
    existing = [col.name for col in c.get_collections().collections]
    if cfg.qdrant_collection not in existing:
        c.create_collection(cfg.qdrant_collection,
            vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
    return c

def _qdrant_up() -> bool:
    if not _QDRANT_OK:
        return False
    try:
        _client().get_collections()
        return True
    except Exception:
        return False

# ── Qdrant upsert ──────────────────────────────────────────────────────────
def upsert(doc_id: str, title: str, version: str, min_role: str,
           chunks: list[str], vectors: list[list[float]]):
    if not _qdrant_up():
        _mem_upsert(doc_id, title, version, min_role, chunks, vectors)
        return
    cfg = get_settings()
    points = [PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{i}")),
        vector=vec,
        payload={"doc_id": doc_id, "title": title, "version": version,
                 "min_role": min_role, "text": chunk, "chunk_idx": i}
    ) for i, (chunk, vec) in enumerate(zip(chunks, vectors))]
    _client().upsert(collection_name=cfg.qdrant_collection, points=points, wait=True)

# ── Qdrant query ────────────────────────────────────────────────────────────
def query(vector: list[float], role: str, k: int = 6) -> list[dict]:
    """RBAC filter applied server-side in Qdrant – restricted payloads never returned."""
    if not _qdrant_up():
        return _mem_query(vector, role, k)
    cfg = get_settings()
    allowed_roles = [r.name for r in RoleLevel if r.value <= RoleLevel[role].value]
    filt = Filter(must=[FieldCondition(key="min_role", match=MatchAny(any=allowed_roles))])
    hits: list[ScoredPoint] = _client().search(
        collection_name=cfg.qdrant_collection,
        query_vector=vector, query_filter=filt, limit=k, with_payload=True)
    return [{"doc_id": h.payload["doc_id"], "title": h.payload["title"],
             "version": h.payload["version"], "min_role": h.payload["min_role"],
             "text": h.payload["text"], "score": round(h.score, 3)} for h in hits]

# ── In-memory fallback (TF-IDF) ─────────────────────────────────────────────
_MEM: list[dict] = []

def _mem_upsert(doc_id, title, version, min_role, chunks, vectors):
    global _MEM
    _MEM = [c for c in _MEM if c["doc_id"] != doc_id]
    for i, (ch, vec) in enumerate(zip(chunks, vectors)):
        _MEM.append({"doc_id": doc_id, "title": title, "version": version,
                     "min_role": min_role, "text": ch, "vector": vec, "chunk_idx": i})

def _cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5
    nb = sum(x*x for x in b) ** 0.5
    return dot / (na * nb + 1e-9)

def _mem_query(vector, role, k):
    allowed = [c for c in _MEM if RoleLevel[c["min_role"]] <= RoleLevel[role]]
    ranked = sorted(allowed, key=lambda c: -_cosine(vector, c["vector"]))[:k]
    return [{k2: v for k2, v in c.items() if k2 != "vector"} | {"score": round(_cosine(vector, c["vector"]), 3)}
            for c in ranked]

def collection_size() -> int:
    try:
        return _client().count(get_settings().qdrant_collection).count
    except Exception:
        return len(_MEM)

def set_min_score(threshold: float = 0.20):
    """Patch _mem_query to enforce a minimum cosine threshold."""
    import app.services.vector_store as _m
    _orig = _m._mem_query
    def _filtered(vector, role, k):
        hits = _orig(vector, role, k*2)
        return [h for h in hits if h["score"] >= threshold][:k]
    _m._mem_query = _filtered
