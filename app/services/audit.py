"""Structured audit log (JSONL). Swap append for DB insert in production."""
import json, time, logging
from pathlib import Path
from app.config import get_settings
import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger()

def write(event: str, **data):
    entry = {"ts": time.time(), "event": event, **data}
    try:
        with Path(get_settings().audit_path).open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    log.info(event, **data)
