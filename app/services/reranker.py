"""Reranker – uses vector scores offline; swap for CrossEncoder in production.
Production: from sentence_transformers import CrossEncoder
            _ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-2-v2")
            scores = _ce.predict([(query, h["text"]) for h in hits])
"""
def rerank(query: str, hits: list[dict], top_k: int = 4) -> list[dict]:
    if not hits:
        return hits
    # Lightweight keyword boost: count query word overlaps as secondary signal
    q_words = set(query.lower().split())
    def boost(h):
        overlap = sum(1 for w in q_words if w in h["text"].lower())
        return h["score"] + overlap * 0.03
    ranked = sorted(hits, key=boost, reverse=True)
    return ranked[:top_k]
