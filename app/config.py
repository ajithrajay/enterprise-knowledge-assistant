from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── LLM (Groq free tier by default) ──────────────────────────────────────
    groq_api_key: str = ""                          # set in Render env vars
    groq_model: str = "llama-3.1-8b-instant"        # free, fast, 131k context

    # fallback to any OpenAI-compatible endpoint (vLLM, OpenAI, etc.)
    llm_base_url: str = ""
    llm_api_key:  str = "none"
    llm_model:    str = "local"

    # ── Auth ──────────────────────────────────────────────────────────────────
    jwt_secret:         str = "change-me-32-chars-minimum-secret"
    jwt_algorithm:      str = "HS256"
    jwt_expire_minutes: int = 480

    # ── Redis (optional) ──────────────────────────────────────────────────────
    redis_url: str = ""

    # ── Misc ──────────────────────────────────────────────────────────────────
    log_level:  str = "info"
    audit_path: str = "/tmp/audit.jsonl"   # /tmp is writable on Render free tier

@lru_cache
def get_settings() -> Settings:
    return Settings()
