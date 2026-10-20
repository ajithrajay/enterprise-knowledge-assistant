from app.services.pipeline import run

def test_vendor_answered():
    r = run("Who approves vendor contracts above 5 lakh?", "employee", "tester")
    assert not r["refused"]
    assert "FIN-VENDOR-v4" in [s["doc_id"] for s in r["sources"]]

def test_leave_answered():
    r = run("How many leave days do full-time employees get?", "employee", "tester")
    assert not r["refused"]

def test_salary_refused_for_intern():
    r = run("What is the L3 salary range?", "intern", "tester")
    assert r["refused"]   # intern cannot see salary docs

def test_salary_answered_for_hr():
    r = run("What is the L3 salary range?", "hr_admin", "hr_carol")
    assert not r["refused"]

def test_graph_laptop():
    r = run("Who approves laptop purchases for contractors in Chennai?", "employee", "tester")
    assert not r["refused"]

def test_out_of_scope_refused():
    r = run("What time does the canteen open?", "employee", "tester")
    assert r["refused"]
