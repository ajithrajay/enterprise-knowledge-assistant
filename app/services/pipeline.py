"""Orchestration: cache → vector retrieval → graph augment → rerank → LLM → validate."""
import time, uuid, logging
from pydantic import ValidationError
from app.models.schemas import RoleLevel
from app.services import cache, audit
from app.services.embedding import embed_one
from app.services.vector_store import query as vquery
from app.services.reranker import rerank
from app.services.graph import approval_chain
from app.services.llm import generate

log = logging.getLogger(__name__)

REFUSAL = ("I couldn't find this in the documents you have access to. "
           "You can raise a ticket below and HR/IT will follow up.")

def run(question: str, role: str, username: str) -> dict:
    t0, rid = time.perf_counter(), uuid.uuid4().hex[:8]

    # 1. Cache hit
    cached = cache.get(question, role)
    if cached:
        audit.write("cache_hit", id=rid, role=role, user=username, query=question)
        return {**cached, "id": rid, "from_cache": True}

    # 2. Semantic retrieval (RBAC enforced in vector store)
    vec = embed_one(question)
    hits = vquery(vec, role, k=8)

    # 3. GraphRAG augmentation
    graph_nodes = approval_chain(question)
    if graph_nodes:
        for node in graph_nodes:
            hits.insert(0, {"doc_id": node.get("doc", "GRAPH"),
                            "title": "Approval Chain", "version": "live",
                            "min_role": "employee", "text":
                            f"{node.get('condition','')}: {node.get('approver','')} approves. "
                            + (f"Budget: {node['budget']}. " if node.get('budget') else ""),
                            "score": 0.99})

    # 4. Cross-encoder rerank
    top = rerank(question, hits, top_k=4)

    ms = round((time.perf_counter() - t0) * 1000)

    if not top:
        audit.write("refused", id=rid, role=role, user=username, query=question, ms=ms)
        return {"id": rid, "answer": REFUSAL, "sources": [], "refused": True, "latency_ms": ms, "from_cache": False}

    # 5. LLM generation + Pydantic validation
    try:
        result = generate(question, top)
        valid_ids = {c["doc_id"] for c in top}
        if not set(result.citations) <= valid_ids or result.confidence < 0.45:
            raise ValueError("citation hallucination or low confidence")
    except (ValidationError, ValueError, Exception) as e:
        log.warning("pipeline fallback %s: %s", rid, e)
        audit.write("refused", id=rid, role=role, user=username, query=question, ms=ms, reason=str(e))
        return {"id": rid, "answer": REFUSAL, "sources": [], "refused": True, "latency_ms": ms, "from_cache": False}

    ms = round((time.perf_counter() - t0) * 1000)
    sources = [{"doc_id": c["doc_id"], "title": c["title"], "version": c["version"],
                "snippet": c["text"], "score": c["score"]}
               for c in top if c["doc_id"] in result.citations]
    out = {"id": rid, "answer": result.answer, "sources": sources,
           "confidence": result.confidence, "refused": False,
           "latency_ms": ms, "from_cache": False}
    cache.set(question, role, out)
    audit.write("answered", id=rid, role=role, user=username, query=question,
                sources=result.citations, confidence=result.confidence, ms=ms)
    return out
