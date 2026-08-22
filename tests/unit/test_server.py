import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib
import os
import json
from unittest.mock import patch
from safelane.adapters.github import app

client = TestClient(app)

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

def sign_payload(payload: dict, secret: str = "secret") -> str:
    body = json.dumps(payload).encode()
    mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"

@pytest.mark.unit
def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "safelane"}

@pytest.mark.unit
def test_invalid_hmac(mock_env):
    payload = {"action": "opened", "pull_request": {"number": 1}}
    response = client.post(
        "/webhook/pr",
        json=payload,
        headers={"x-hub-signature-256": "sha256=invalid", "x-github-event": "pull_request"}
    )
    assert response.status_code == 401
    assert "signature" in response.json()["detail"].lower()

@pytest.mark.unit
def test_valid_pr_event(mock_env):
    payload = {
        "action": "opened",
        "pull_request": {"number": 1, "updated_at": "2024-01-01T00:00:00Z"},
        "repository": {"full_name": "owner/repo"}
    }
    body = json.dumps(payload).encode("utf-8")
    mac = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    sig = f"sha256={mac}"
    
    response = client.post(
        "/webhook/pr",
        content=body,
        headers={"x-hub-signature-256": sig, "x-github-event": "pull_request", "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}

@pytest.mark.unit
def test_non_pr_event(mock_env):
    payload = {"action": "created"}
    body = json.dumps(payload).encode("utf-8")
    mac = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    sig = f"sha256={mac}"
    
    response = client.post(
        "/webhook/pr",
        content=body,
        headers={"x-hub-signature-256": sig, "x-github-event": "issue_comment", "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

@pytest.mark.unit
def test_missing_repo_registration(mock_env, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN") # Causes get_repo_context to return None
    payload = {
        "action": "opened",
        "pull_request": {"number": 1},
        "repository": {"full_name": "owner/missing"}
    }
    body = json.dumps(payload).encode("utf-8")
    mac = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    sig = f"sha256={mac}"
    
    response = client.post(
        "/webhook/pr",
        content=body,
        headers={"x-hub-signature-256": sig, "x-github-event": "pull_request", "Content-Type": "application/json"}
    )
    assert response.status_code == 404
