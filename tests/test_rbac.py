from app.services.embedding import embed_one
from app.services.vector_store import query as vquery

def _ids(role, q):
    return [h["doc_id"] for h in vquery(embed_one(q), role)]

def test_intern_no_salary():
    assert "HR-SALARY-v2" not in _ids("intern", "salary range L3")

def test_hr_sees_salary():
    assert "HR-SALARY-v2" in _ids("hr_admin", "salary range L3 band")

def test_employee_no_salary():
    assert "HR-SALARY-v2" not in _ids("employee", "salary band L4")

def test_vendor_retrieval():
    ids = _ids("employee", "vendor contract approval above 5 lakh")
    assert "PROC-VENDOR-v4" in ids

def test_out_of_scope():
    hits = vquery(embed_one("cricket match score yesterday"), "employee", k=4)
    assert all(h["score"] < 0.5 for h in hits)
