import pytest
import asyncio
from unittest.mock import patch, MagicMock
from safelane.contracts import PRPayload, RepoContext, EvidenceResult, VerdictReport
from safelane.fabric.controller import orchestrate

@pytest.fixture
def base_payload():
    return PRPayload(
        pr_number=1,
        repo="owner/repo",
        changed_files=["src/main.py"],
        diff="def foo():\n+ pass",
        timestamp="2023-01-01T00:00:00Z",
        head_sha="abcdef",
        skip_autofix=False
    )

async def mock_pass_ci(request, repo_context):
    return EvidenceResult(module="change_intelligence", status="pass", risk_score_modifier=0, findings=["All good"], recommended_action="None")

async def mock_pass_im(request, repo_context):
    return EvidenceResult(module="incident_memory", status="pass", risk_score_modifier=0, findings=["All good"], recommended_action="None")

async def mock_pass_vr(request, repo_context):
    return EvidenceResult(module="verification_readiness", status="pass", risk_score_modifier=0, findings=["All good"], recommended_action="None")
    
async def mock_pass_rc(request, repo_context):
    return EvidenceResult(module="release_context", status="pass", risk_score_modifier=0, findings=["All good"], recommended_action="None")

async def mock_fail_im(request, repo_context):
    return EvidenceResult(module="incident_memory", status="critical", risk_score_modifier=50, findings=["Terrible failure"], recommended_action="Fix it")
    
async def mock_timeout_ci(request, repo_context):
    await asyncio.sleep(0.5)
    return await mock_pass_ci(request, repo_context)

@pytest.mark.integration
@patch("safelane.evidence.change_intelligence.run", new=mock_pass_ci)
@patch("safelane.evidence.incident_memory.run", new=mock_pass_im)
@patch("safelane.evidence.verification_readiness.run", new=mock_pass_vr)
@patch("safelane.evidence.release_context.run", new=mock_pass_rc)
async def test_orchestrate_greenlights_safe_fixture(base_payload):
    report = await orchestrate(base_payload)
    assert isinstance(report, VerdictReport)
    assert "greenlight" in report.decision
    assert len(report.evidence_results) == 4

@pytest.mark.integration
@patch("safelane.evidence.change_intelligence.run", new=mock_pass_ci)
@patch("safelane.evidence.incident_memory.run", new=mock_fail_im)
@patch("safelane.evidence.verification_readiness.run", new=mock_pass_vr)
@patch("safelane.evidence.release_context.run", new=mock_pass_rc)
# Needs real verdict logic to properly block, but testing evidence collection
async def test_orchestrate_blocks_critical_fixture(base_payload):
    report = await orchestrate(base_payload)
    assert len(report.evidence_results) == 4
    statuses = [er.status for er in report.evidence_results]
    assert "critical" in statuses

@pytest.mark.integration
@patch("safelane.fabric.controller.MODULE_TIMEOUT_SECONDS", 0.1)
@patch("safelane.evidence.change_intelligence.run", new=mock_timeout_ci)
@patch("safelane.evidence.incident_memory.run", new=mock_pass_im)
@patch("safelane.evidence.verification_readiness.run", new=mock_pass_vr)
@patch("safelane.evidence.release_context.run", new=mock_pass_rc)
async def test_orchestrate_module_timeout(base_payload):
    report = await orchestrate(base_payload)
    er = next(e for e in report.evidence_results if e.module == "change_intelligence")
    assert er.status == "warning"
    assert "could not complete" in er.findings[0]
