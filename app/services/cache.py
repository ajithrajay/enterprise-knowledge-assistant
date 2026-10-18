"""Redis semantic cache. Falls back to no-op when Redis is unavailable."""
import hashlib, json, logging
from app.config import get_settings

log = logging.getLogger(__name__)
_r = None

def _redis():
    global _r
    if _r is not None:
        return _r
    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis
        _r = redis.from_url(url, socket_connect_timeout=1, decode_responses=True)
        _r.ping()
        return _r
    except Exception as e:
        log.warning("Redis unavailable (%s) – caching disabled", e)
        return None

def _key(query: str, role: str) -> str:
    return "ka:" + hashlib.sha256(f"{role}:{query.lower().strip()}".encode()).hexdigest()[:16]

def get(query: str, role: str) -> dict | None:
    r = _redis()
    if not r:
        return None
    v = r.get(_key(query, role))
    return json.loads(v) if v else None

def set(query: str, role: str, value: dict, ttl: int = 3600):
    r = _redis()
    if r:
        r.setex(_key(query, role), ttl, json.dumps(value))

def invalidate_prefix(prefix: str):
    r = _redis()
    if r:
        for k in r.scan_iter(f"ka:{prefix}*"):
            r.delete(k)
