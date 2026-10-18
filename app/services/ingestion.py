import re, io, logging
from app.services import embedding as _emb
from app.services import vector_store as _vs

log = logging.getLogger(__name__)

def _smart_chunk(text: str, max_len: int = 350, overlap: int = 60) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, buf, buf_len = [], [], 0
    for s in sentences:
        s = s.strip()
        if not s: continue
        if buf_len + len(s) > max_len and buf:
            chunks.append(" ".join(buf))
            tail, tail_len = [], 0
            for b in reversed(buf):
                if tail_len + len(b) > overlap: break
                tail.insert(0, b); tail_len += len(b)
            buf, buf_len = tail, tail_len
        buf.append(s); buf_len += len(s)
    if buf:
        chunks.append(" ".join(buf))
    return [c for c in chunks if len(c) > 30]

def ingest_text(doc_id: str, title: str, version: str, min_role: str, text: str) -> int:
    chunks = _smart_chunk(text)
    # refit vocab on everything seen so far + new chunks
    all_texts = [c["text"] for c in _vs._MEM] + chunks
    if all_texts:
        _emb.refit(all_texts)
    # re-embed all existing chunks with new vocab then upsert new ones
    for c in _vs._MEM:
        c["vector"] = _emb.embed([c["text"]])[0]
    vectors = _emb.embed(chunks)
    _vs.upsert(doc_id, title, version, min_role, chunks, vectors)
    log.info("ingested %s – %d chunks", doc_id, len(chunks))
    return len(chunks)

def ingest_pdf(doc_id: str, title: str, version: str, min_role: str, pdf_bytes: bytes) -> int:
    from pypdf import PdfReader
    import io as _io
    reader = PdfReader(_io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return ingest_text(doc_id, title, version, min_role, text)
