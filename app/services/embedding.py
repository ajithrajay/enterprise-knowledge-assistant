"""Offline TF-IDF embedding (no HuggingFace needed).
Swap get_encoder() / embed() for SentenceTransformer in production:
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("all-MiniLM-L6-v2")
    return enc.encode(texts, normalize_embeddings=True).tolist()
"""
import math, re
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer

# Fixed 256-dim vocabulary built from seed corpus (replaced at startup after ingest)
_state: dict = {"vec": None, "dim": 256}

def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x*x for x in v)) or 1.0
    return [x/n for x in v]

def _fit(corpus: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer as TV
    v = TV(max_features=_state["dim"], ngram_range=(1,2), sublinear_tf=True)
    v.fit(corpus)
    _state["vec"] = v

def embed(texts: list[str]) -> list[list[float]]:
    if _state["vec"] is None:
        # cold start: fit on query text itself (sparse but safe)
        _fit(texts)
    mat = _state["vec"].transform(texts)
    return [_norm(row.toarray()[0].tolist()) for row in mat]

def embed_one(text: str) -> list[float]:
    return embed([text])[0]

def refit(corpus: list[str]):
    """Called after bulk ingest to retrain the vocabulary."""
    _fit(corpus)
