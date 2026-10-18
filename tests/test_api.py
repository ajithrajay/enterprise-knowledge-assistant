import pytest
from tests.conftest import auth

def test_health(client):
    assert client.get("/health").json()["ok"] is True

def test_login_ok(client):
    r = client.post("/api/auth/token", data={"username":"alice","password":"alice123"})
    assert r.status_code == 200 and "access_token" in r.json()

def test_login_bad(client):
    r = client.post("/api/auth/token", data={"username":"alice","password":"bad"})
    assert r.status_code == 401

def test_chat_requires_auth(client):
    r = client.post("/api/chat", json={"query":"test"})
    assert r.status_code == 401

def test_chat_works(client):
    r = client.post("/api/chat", json={"query":"How many leave days?"},
                    headers=auth("employee"))
    assert r.status_code == 200 and not r.json()["refused"]

def test_ticket_confirm_flow(client):
    r = client.post("/api/ticket", json={"summary":"Need help with payslip","confirmed":False},
                    headers=auth("employee"))
    assert r.json()["status"] == "needs_confirmation"
    r2 = client.post("/api/ticket", json={"summary":"Need help with payslip","confirmed":True},
                     headers=auth("employee"))
    assert r2.json()["status"] == "created"

def test_ingest_requires_hr_admin(client):
    r = client.post("/api/admin/ingest/text",
        json={"title":"Test","version":"v1","min_role":"employee","text":"Test content here."},
        headers=auth("employee"))
    assert r.status_code == 403

def test_analytics_requires_manager(client):
    r = client.get("/api/analytics", headers=auth("intern"))
    assert r.status_code == 403

def test_analytics_ok(client):
    r = client.get("/api/analytics", headers=auth("manager"))
    assert r.status_code == 200 and "asked" in r.json()
