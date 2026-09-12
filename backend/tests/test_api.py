import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "running" in response.json()["message"]

def test_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "lean_installed" in data

def test_examples():
    response = client.get("/api/examples")
    assert response.status_code == 200
    examples = response.json()
    assert len(examples) >= 4
    assert any("Identity" in ex["title"] for ex in examples)

def test_formalize_mock():
    payload = {
        "english_statement": "For all natural numbers n, n + 0 = n",
        "domain_hint": "arithmetic"
    }
    response = client.post("/api/formalize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "theorem" in data["lean_code"]
    assert "sorry" in data["lean_code"]

def test_verify_code():
    code = "theorem test_thm (n : Nat) : n + 0 = n := by\n  rfl"
    response = client.post("/api/verify", json={"lean_code": code})
    assert response.status_code == 200
    data = response.json()
    assert "is_valid" in data

def test_prove_fast_hammer():
    # A theorem that is true by reflexivity or omega
    code = "theorem add_zero_thm (n : Nat) : n + 0 = n := by\n  sorry"
    response = client.post("/api/prove", json={
        "lean_code": code,
        "strategy": "fast_hammer"
    })
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
