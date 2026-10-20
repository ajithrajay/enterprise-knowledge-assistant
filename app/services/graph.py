"""
GraphRAG approval-chain lookup — Nexova Technologies.
Switches to live Neo4j when NEO4J_URI env var is set; otherwise uses
the in-memory graph that mirrors the seed corpus exactly.
"""
import logging
log = logging.getLogger(__name__)

# ── In-memory graph (mirrors COMPANY_DOCS approval chains) ──────────────────
_GRAPH = {
    "vendor_contract": [
        {"condition": "up to Rs 1 lakh",          "approver": "Department Manager",           "doc": "FIN-VENDOR-v4"},
        {"condition": "Rs 1 lakh to Rs 5 lakh",   "approver": "BU Head",                      "doc": "FIN-VENDOR-v4"},
        {"condition": "Rs 5 lakh to Rs 25 lakh",  "approver": "Finance Head + COO",           "doc": "FIN-VENDOR-v4"},
        {"condition": "above Rs 25 lakh",          "approver": "CFO (Meera Krishnamurthy)",    "doc": "FIN-VENDOR-v4"},
        {"condition": "above Rs 1 crore",          "approver": "CFO + Board notification",     "doc": "FIN-VENDOR-v4"},
    ],
    "procurement": [
        {"condition": "up to Rs 1 lakh",           "approver": "Department Manager",           "doc": "FIN-VENDOR-v4"},
        {"condition": "Rs 1 lakh to Rs 5 lakh",   "approver": "BU Head, 3 vendor quotes",     "doc": "FIN-VENDOR-v4"},
        {"condition": "Rs 5 lakh to Rs 25 lakh",  "approver": "Finance Head + COO",           "doc": "FIN-VENDOR-v4"},
        {"condition": "above Rs 25 lakh",          "approver": "CFO",                          "doc": "FIN-VENDOR-v4"},
    ],
    "laptop_purchase": [
        {"condition": "contractors at Chennai office",   "approver": "Site IT Lead (Ravi Kumar)",    "budget": "Rs 75,000 per device", "doc": "IT-EQUIPMENT-v3"},
        {"condition": "contractors at Bangalore HQ",     "approver": "IT Manager",                   "budget": "Rs 80,000 per device", "doc": "IT-EQUIPMENT-v3"},
        {"condition": "permanent employees",             "approver": "IT Helpdesk (standard issue)",  "budget": "per band allocation",  "doc": "IT-EQUIPMENT-v3"},
    ],
    "leave_request": [
        {"condition": "up to 5 consecutive days",        "approver": "Direct Manager",               "doc": "HR-LEAVE-v5"},
        {"condition": "more than 5 consecutive days",    "approver": "Manager + HRBP",               "doc": "HR-LEAVE-v5"},
        {"condition": "Leave Without Pay",               "approver": "Manager + HRBP",               "doc": "HR-LEAVE-v5"},
    ],
    "travel_domestic": [
        {"condition": "L2-L4 domestic travel",          "approver": "Direct Manager",               "doc": "FIN-TRAVEL-v4"},
        {"condition": "L5 domestic travel",             "approver": "BU Head",                      "doc": "FIN-TRAVEL-v4"},
        {"condition": "L6+ domestic travel",            "approver": "COO",                          "doc": "FIN-TRAVEL-v4"},
    ],
    "international_travel": [
        {"condition": "any international travel",       "approver": "BU Head + CFO",                "doc": "FIN-TRAVEL-v4"},
    ],
    "hiring": [
        {"condition": "L2-L4 hire",                     "approver": "BU Head",                      "doc": "APPROVE-CHAINS-v2"},
        {"condition": "L5+ hire",                       "approver": "HR Committee (CPO + COO + BU Head)", "doc": "APPROVE-CHAINS-v2"},
    ],
    "promotion": [
        {"condition": "L4 and below",                   "approver": "BU Head after appraisal",      "doc": "APPROVE-CHAINS-v2"},
        {"condition": "L5+",                            "approver": "HR Committee",                 "doc": "APPROVE-CHAINS-v2"},
    ],
    "production_deployment": [
        {"condition": "standard deployment (Thursday window)", "approver": "Tech Lead + QA Lead + Product Manager", "doc": "ENG-SDLC-v3"},
        {"condition": "emergency hotfix",                      "approver": "CTO + CISO",                            "doc": "ENG-SDLC-v3"},
    ],
    "saas_procurement": [
        {"condition": "any new SaaS tool",                    "approver": "IT security review + BU Head",           "doc": "FIN-VENDOR-v4"},
        {"condition": "above Rs 50,000 per year",             "approver": "IT security + BU Head + Finance Head",   "doc": "FIN-VENDOR-v4"},
    ],
    "salary_revision": [
        {"condition": "annual increment",                     "approver": "HR Committee + CFO",                     "doc": "HR-SALARY-v3"},
        {"condition": "off-cycle correction",                 "approver": "CFO",                                    "doc": "HR-SALARY-v3"},
    ],
    "discount_authority": [
        {"condition": "up to 10% discount",                   "approver": "Sales Manager",                          "doc": "SALES-PROCESS-v2"},
        {"condition": "10-20% discount",                      "approver": "VP Sales (Pooja Iyer)",                   "doc": "SALES-PROCESS-v2"},
        {"condition": "above 20% discount",                   "approver": "CEO (Rajesh Nair)",                       "doc": "SALES-PROCESS-v2"},
    ],
}

_KEYWORDS = {
    # vendor / procurement
    "vendor": "vendor_contract", "contract": "vendor_contract", "procurement": "procurement",
    "purchase order": "procurement", "po ": "procurement",
    # hardware
    "laptop": "laptop_purchase", "hardware": "laptop_purchase", "device": "laptop_purchase",
    "equipment": "laptop_purchase",
    # leave
    "leave": "leave_request", "absence": "leave_request", "time off": "leave_request",
    # travel
    "international": "international_travel", "abroad": "international_travel",
    "domestic travel": "travel_domestic", "travel": "travel_domestic",
    # hiring / promotion
    "hire": "hiring", "recruit": "hiring", "headcount": "hiring",
    "promot": "promotion", "promotion": "promotion",
    # production
    "production deploy": "production_deployment", "hotfix": "production_deployment",
    "release": "production_deployment",
    # saas
    "saas": "saas_procurement", "subscription": "saas_procurement", "software tool": "saas_procurement",
    # salary
    "salary": "salary_revision", "increment": "salary_revision", "pay revision": "salary_revision",
    # sales discount
    "discount": "discount_authority",
}


def _neo4j_lookup(intent: str) -> list[dict] | None:
    try:
        import os
        from neo4j import GraphDatabase
        uri  = os.getenv("NEO4J_URI",  "bolt://localhost:7687")
        auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASS", "neo4j"))
        with GraphDatabase.driver(uri, auth=auth) as driver:
            with driver.session() as session:
                rows = session.run(
                    "MATCH (a:ApprovalChain {intent: $intent})-[:HAS_RULE]->(r:Rule) "
                    "RETURN r.condition AS condition, r.approver AS approver, "
                    "r.budget AS budget, r.doc AS doc",
                    intent=intent
                ).data()
                return rows if rows else None
    except Exception as e:
        log.debug("Neo4j unavailable: %s", e)
        return None


def approval_chain(query: str) -> list[dict]:
    q = query.lower()
    intent = next((v for k, v in _KEYWORDS.items() if k in q), None)
    if not intent:
        return []
    rows = _neo4j_lookup(intent)
    return rows if rows is not None else _GRAPH.get(intent, [])

# doc → min_role mapping for RBAC in graph results
_DOC_MIN_ROLE = {
    "HR-SALARY-v3": "hr_admin",
    "SALES-CLIENT-v2": "manager",
    "FIN-BUDGET-v2": "manager",
    "COMPLIANCE-STATUTORY-v2": "manager",
}
from app.models.schemas import RoleLevel

def approval_chain_rbac(query: str, role: str) -> list[dict]:
    """Like approval_chain but filters nodes the role cannot access."""
    nodes = approval_chain(query)
    result = []
    for n in nodes:
        doc = n.get("doc", "")
        min_r = _DOC_MIN_ROLE.get(doc, "intern")
        if RoleLevel[role] >= RoleLevel[min_r]:
            result.append(n)
    return result
