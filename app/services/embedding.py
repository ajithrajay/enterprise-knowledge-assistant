"""Offline TF-IDF embedding (no HuggingFace needed).
Swap embed() for SentenceTransformer in production:
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("all-MiniLM-L6-v2")
    return enc.encode(texts, normalize_embeddings=True).tolist()
"""
import re, math
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

_state: dict = {"vec": None}


def _analyzer(text: str):
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in ENGLISH_STOP_WORDS:
            continue
        for suf in ("ation", "ing", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[:-len(suf)]
                break
        out.append(w)
    return out


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fit(corpus: list[str]):
    v = TfidfVectorizer(analyzer=_analyzer, sublinear_tf=True)  # full vocab, no max_features
    v.fit(corpus)
    _state["vec"] = v


def embed(texts: list[str]) -> list[list[float]]:
    if _state["vec"] is None:
        _fit(texts)  # cold start only
    mat = _state["vec"].transform(texts)
    return [_norm(row.toarray()[0].tolist()) for row in mat]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
    

def refit(corpus: list[str]):
    """Called after ingest to retrain the vocabulary."""
    _fit(corpus)