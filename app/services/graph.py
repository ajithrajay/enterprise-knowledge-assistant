"""GraphRAG – Neo4j approval-chain lookup.
Falls back to an in-memory dict when Neo4j is unavailable (offline dev / testing)."""
import logging
log = logging.getLogger(__name__)

# ── in-memory graph (covers the seed corpus) ─────────────────────────────
_GRAPH = {
    "vendor_contract": [
        {"condition": "up to Rs 5 lakh",    "approver": "Department Manager",   "doc": "PROC-VENDOR-v4"},
        {"condition": "Rs 5–25 lakh",        "approver": "Finance Head",         "doc": "PROC-VENDOR-v4"},
        {"condition": "above Rs 25 lakh",    "approver": "CFO",                  "doc": "PROC-VENDOR-v4"},
    ],
    "laptop_purchase": [
        {"condition": "contractors at Chennai office", "approver": "Site IT Lead",
         "budget": "Rs 75,000 per device", "doc": "IT-LAPTOP-v1"},
    ],
    "leave_request": [
        {"condition": "over 5 consecutive days", "approver": "Manager", "doc": "HR-LEAVE-v3"},
    ],
    "international_travel": [
        {"condition": "any international trip", "approver": "Department Head", "doc": "FIN-TRAVEL-v2"},
    ],
}

_KEYWORDS = {
    "vendor": "vendor_contract", "contract": "vendor_contract",
    "laptop": "laptop_purchase", "hardware": "laptop_purchase", "device": "laptop_purchase",
    "leave": "leave_request", "absence": "leave_request",
    "international": "international_travel", "travel": "international_travel",
}

def _neo4j_lookup(intent: str) -> list[dict] | None:
    """Try Neo4j if available. Returns None if not reachable."""
    try:
        import os
        from neo4j import GraphDatabase
        uri  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASS", "neo4j"))
        with GraphDatabase.driver(uri, auth=auth) as driver:
            with driver.session() as session:
                rows = session.run(
                    "MATCH (a:ApprovalChain {intent: $intent})-[:HAS_RULE]->(r:Rule) "
                    "RETURN r.condition AS condition, r.approver AS approver, "
                    "r.budget AS budget, r.doc AS doc", intent=intent).data()
                return rows if rows else None
    except Exception as e:
        log.debug("Neo4j unavailable: %s", e)
        return None

def approval_chain(query: str) -> list[dict]:
    """Return approval rules relevant to the query (multi-hop ready)."""
    q_lower = query.lower()
    intent = next((v for k, v in _KEYWORDS.items() if k in q_lower), None)
    if not intent:
        return []
    rows = _neo4j_lookup(intent)
    if rows is not None:
        return rows
    return _GRAPH.get(intent, [])
