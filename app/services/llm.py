"""
LLM generation layer.
Priority: Groq (free) → generic OpenAI-compat endpoint → offline extractive.

Key design: confidence is computed from retrieval scores, NOT asked from the LLM.
Llama 3.1 on Groq unreliably returns 0.0–0.1 confidence even for correct answers,
which caused false refusals. We own the confidence calculation here.
"""
import json, logging
import httpx
from pydantic import ValidationError
from app.config import get_settings
from app.models.schemas import LLMAnswer

log = logging.getLogger(__name__)

# Ask LLM only for answer + citations. No confidence field.
SYSTEM = (
    "You are a precise enterprise knowledge assistant. "
    "Answer ONLY using the provided context passages. Be concise and factual. "
    "If several passages seem to conflict, prefer the most specific one. "
    "Respond ONLY as valid JSON with NO markdown fences, exactly this shape: "
    '{"answer": "<your answer>", "citations": ["DOC-ID-1", "DOC-ID-2"]}. '
    "citations must be the exact document IDs from the context (e.g. HR-LEAVE-v5). "
    "If the context does not contain enough information, set citations to [] "
    'and set answer to "I could not find this in the available documents."'
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Used ONLY by the offline extractive fallback (no LLM available to say "not found").
# With a real LLM, it decides relevance itself and this value is never consulted.
MIN_EXTRACTIVE_SCORE = 0.25


def _compute_confidence(answer: str, citations: list[str], ctx: list[dict]) -> float:
    """
    Compute confidence from retrieval evidence — never trust LLM self-scoring.
    - Base: average score of cited chunks (0–1 cosine similarity)
    - Boost: +0.15 if answer is non-refusal and citations are non-empty
    - Penalty: -0.30 if answer contains uncertainty phrases
    """
    refusal_phrases = ["could not find", "not find", "insufficient", "don't have", "no information"]
    uncertainty_phrases = ["might", "possibly", "not sure", "unclear", "i believe"]

    # If LLM explicitly says it couldn't find it
    answer_lower = answer.lower()
    if any(p in answer_lower for p in refusal_phrases) or not citations:
        return 0.0

    # Base score from top cited chunks
    cited_scores = [c["score"] for c in ctx if c["doc_id"] in citations]
    base = (sum(cited_scores) / len(cited_scores)) if cited_scores else 0.35

    # Scale up — retrieval scores in TF-IDF are low (0.3–0.6 range)
    # Map 0.38 → ~0.75, 0.55 → ~0.90
    scaled = min(0.97, base * 1.8 + 0.05)

    # Small penalty for hedging language
    if any(p in answer_lower for p in uncertainty_phrases):
        scaled = max(0.40, scaled - 0.15)

    return round(scaled, 2)


def _call_groq(messages: list[dict]) -> dict:
    cfg = get_settings()
    r = httpx.post(GROQ_URL, timeout=30,
        headers={"Authorization": f"Bearer {cfg.groq_api_key}",
                 "Content-Type": "application/json"},
        json={"model": cfg.groq_model, "temperature": 0,
              "response_format": {"type": "json_object"},
              "messages": messages})
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def _call_openai_compat(messages: list[dict]) -> dict:
    cfg = get_settings()
    r = httpx.post(f"{cfg.llm_base_url}/chat/completions", timeout=45,
        headers={"Authorization": f"Bearer {cfg.llm_api_key}",
                 "Content-Type": "application/json"},
        json={"model": cfg.llm_model, "temperature": 0,
              "response_format": {"type": "json_object"},
              "messages": messages})
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def _extractive(ctx: list[dict]) -> dict:
    """Offline fallback: return the top chunk verbatim. Has no judgment of its own,
    so it refuses when the best real (non-graph) hit is too weak."""
    real = [c for c in ctx if c.get("version") != "live"]   # ignore graph chunks
    if not real or max(c["score"] for c in real) < MIN_EXTRACTIVE_SCORE:
        return {"answer": "I could not find this in the available documents.",
                "citations": []}
    top = ctx[0]
    return {
        "answer":    top["text"],
        "citations": list(dict.fromkeys(c["doc_id"] for c in ctx[:2])),
    }


def generate(query: str, ctx: list[dict]) -> LLMAnswer:
    cfg = get_settings()
    context_block = "\n".join(f"[{c['doc_id']}] {c['text']}" for c in ctx)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": f"Context:\n{context_block}\n\nQuestion: {query}"},
    ]

    raw: dict | None = None
    if cfg.groq_api_key:
        try:
            raw = _call_groq(messages)
        except Exception as e:
            log.warning("Groq failed, falling back: %s", e)

    if raw is None and cfg.llm_base_url:
        try:
            raw = _call_openai_compat(messages)
        except Exception as e:
            log.warning("OpenAI-compat failed, falling back: %s", e)

    if raw is None:
        raw = _extractive(ctx)

    # Strip any LLM-generated confidence — we compute it ourselves
    raw.pop("confidence", None)

    citations = raw.get("citations", [])
    answer    = raw.get("answer", "")

    # Compute confidence from retrieval evidence
    confidence = _compute_confidence(answer, citations, ctx)

    return LLMAnswer(answer=answer, citations=citations, confidence=confidence)