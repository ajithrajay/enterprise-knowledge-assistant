"""
LLM generation layer.
Priority: Groq (free) → generic OpenAI-compat endpoint → offline extractive.
"""
import json, logging
import httpx
from pydantic import ValidationError
from app.config import get_settings
from app.models.schemas import LLMAnswer

log = logging.getLogger(__name__)

SYSTEM = (
    "You are a precise enterprise knowledge assistant. "
    "Answer ONLY from the provided context passages. "
    "Respond ONLY as valid JSON, no markdown fences: "
    '{"answer": "<concise factual answer>", "citations": ["DOC-ID-1", ...], "confidence": 0.0-1.0}. '
    "If the context is insufficient, set citations to [] and state you could not find the answer."
)

# ── Groq ──────────────────────────────────────────────────────────────────────
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

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

# ── Generic OpenAI-compatible (vLLM / OpenAI) ─────────────────────────────────
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

# ── Offline extractive fallback ───────────────────────────────────────────────
def _extractive(ctx: list[dict]) -> dict:
    top = ctx[0]
    return {
        "answer": top["text"],
        "citations": list(dict.fromkeys(c["doc_id"] for c in ctx[:2])),
        "confidence": min(0.85, top["score"] + 0.30),
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
    return LLMAnswer(**raw)
