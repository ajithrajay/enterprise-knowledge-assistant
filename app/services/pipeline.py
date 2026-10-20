"""Orchestration: cache → vector retrieval → graph augment → rerank → LLM → validate."""
import time, uuid, logging
from pydantic import ValidationError
from app.services import cache, audit
from app.services.embedding import embed_one
from app.services.vector_store import query as vquery
from app.services.reranker import rerank
from app.services.graph import approval_chain_rbac
from app.services.llm import generate

log = logging.getLogger(__name__)

REFUSAL = ("I couldn't find this in the documents you have access to. "
           "You can raise a ticket below and HR/IT will follow up.")


def _elapsed_ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def _refuse(rid, role, username, question, t0, reason=None):
    ms = _elapsed_ms(t0)                      # computed at refusal time, not before the LLM call
    extra = {"reason": reason} if reason else {}
    audit.write("refused", id=rid, role=role, user=username,
                query=question, ms=ms, **extra)
    return {"id": rid, "answer": REFUSAL, "sources": [],
            "refused": True, "latency_ms": ms, "from_cache": False}


def run(question: str, role: str, username: str) -> dict:
    t0, rid = time.perf_counter(), uuid.uuid4().hex[:8]

    # 1. Cache hit
    cached = cache.get(question, role)
    if cached:
        audit.write("cache_hit", id=rid, role=role, user=username, query=question)
        return {**cached, "id": rid, "from_cache": True}

    # 2. Semantic retrieval (RBAC enforced in vector store)
    vec = embed_one(question)
    hits = vquery(vec, role, k=15)

    # 3. GraphRAG augmentation: build ONE combined chunk, kept separate from real hits
    graph_hits = []
    graph_nodes = approval_chain_rbac(question, role)
    if graph_nodes:
        lines = []
        for n in graph_nodes:
            line = f"{n.get('condition', '')}: {n.get('approver', '')} approves."
            if n.get("budget"):
                line += f" Budget: {n['budget']}."
            lines.append(line)
        graph_hits.append({
            "doc_id": graph_nodes[0].get("doc", "GRAPH"),
            "title": "Approval Chain", "version": "live",
            "min_role": "employee",
            "text": "Approval chain: " + " ".join(lines),
            "score": 0.99,
        })

    # 4. Rerank real documents only, then add the graph chunk.
    #    Real hits always get their slots; the graph chunk can't crowd them out.
    real = rerank(question, hits, top_k=5)
    top = (graph_hits + real)[:6]

    if not real and not graph_hits:
        return _refuse(rid, role, username, question, t0, reason="no_hits")

    # 5. LLM generation + validation
    try:
        result = generate(question, top)

        # No backfill: empty citations means the LLM found nothing, so refuse honestly.
        if not result.citations:
            raise ValueError("llm_found_nothing (no citations)")

        valid_ids = {c["doc_id"] for c in top}
        hallucinated = not set(result.citations) <= valid_ids
        low_conf = result.confidence < 0.10
        if hallucinated or low_conf:
            raise ValueError(
                f"hallucinated_citations={hallucinated} low_conf={low_conf} ({result.confidence:.2f})")

    except (ValidationError, ValueError, Exception) as e:
        log.warning("pipeline fallback %s: %s", rid, e)
        return _refuse(rid, role, username, question, t0, reason=str(e))

    ms = _elapsed_ms(t0)
    sources = [
        {"doc_id": c["doc_id"], "title": c["title"],
         "version": c["version"], "snippet": c["text"], "score": c["score"]}
        for c in top if c["doc_id"] in result.citations
    ]
    out = {"id": rid, "answer": result.answer, "sources": sources,
           "confidence": result.confidence, "refused": False,
           "latency_ms": ms, "from_cache": False}
    cache.set(question, role, out)
    audit.write("answered", id=rid, role=role, user=username,
                query=question, sources=result.citations,
                confidence=result.confidence, ms=ms)
    return out