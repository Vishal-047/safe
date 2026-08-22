import os
import pytest
from types import SimpleNamespace
from safelane.adapters.foundry import (
    get_foundry_client,
    setup_tracing,
    trace_agent_call,
    trace_orchestrate,
    check_content_safety,
    apply_policy_guardrails,
    evaluate_quality
)

@pytest.fixture(autouse=True)
def clear_env():
    # Ensure environment variables are clear for tests
    vars_to_clear = [
        "AZURE_FOUNDRY_PROJECT_CONNECTION_STRING",
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "AZURE_CONTENT_SAFETY_ENDPOINT",
        "AZURE_CONTENT_SAFETY_KEY",
    ]
    for var in vars_to_clear:
        if var in os.environ:
            del os.environ[var]

@pytest.mark.unit
def test_get_foundry_client_missing_env():
    assert get_foundry_client() is None

@pytest.mark.unit
def test_setup_tracing_missing_env():
    # Should not raise any exceptions
    setup_tracing()

@pytest.mark.unit
def test_trace_agent_call(monkeypatch):
    monkeypatch.setitem(os.environ, "APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    with pytest.MonkeyPatch.context() as m:
        m.setattr("builtins.__import__", lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError) if name == "opentelemetry" else __import__(name, *args, **kwargs))
        with trace_agent_call("test_agent") as span:
            assert span is None

@pytest.mark.unit
def test_trace_orchestrate(monkeypatch):
    with pytest.MonkeyPatch.context() as m:
        m.setattr("builtins.__import__", lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError) if name == "opentelemetry" else __import__(name, *args, **kwargs))
        with trace_orchestrate(123, "owner/repo") as span:
            assert span is None

@pytest.mark.unit
async def test_check_content_safety_missing_env():
    # Should be default-safe when missing configuration
    is_safe = await check_content_safety("some text")
    assert is_safe is True

@pytest.mark.unit
def test_apply_policy_guardrails():
    # Construct mock verdict report and pr payload
    verdict_report = SimpleNamespace(confidence_score=25, decision="block")
    pr_payload = SimpleNamespace(pr_number=42, repo="owner/repo")
    
    audit_entry = apply_policy_guardrails(verdict_report, pr_payload)
    
    assert audit_entry is not None
    assert audit_entry["score"] == 25
    assert audit_entry["decision"] == "block"
    assert audit_entry["escalated"] is True
    assert "timestamp" in audit_entry
    assert audit_entry["pr_number"] == 42
    assert audit_entry["repo"] == "owner/repo"

@pytest.mark.unit
async def test_evaluate_quality():
    result = await evaluate_quality("generated text", "reference text")
    assert result is None
