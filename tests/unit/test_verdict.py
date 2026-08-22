import pytest
from safelane.contracts import EvidenceResult, SecurityFinding, VerdictReport, MODULE_WEIGHTS
from safelane.fabric.verdict import compute_score, decide, build_risk_brief, build_rollback_playbook, build_verdict

@pytest.fixture
def clean_evidence():
    return [
        EvidenceResult(module="change_intelligence", status="pass", risk_score_modifier=0, findings=[], recommended_action=""),
        EvidenceResult(module="incident_memory", status="pass", risk_score_modifier=0, findings=[], recommended_action="")
    ]

@pytest.fixture
def critical_evidence():
    return [
        EvidenceResult(module="change_intelligence", status="critical", risk_score_modifier=100, findings=[], recommended_action="")
    ]

@pytest.mark.unit
def test_module_weights_sum_to_one():
    assert sum(MODULE_WEIGHTS.values()) == 1.0

@pytest.mark.unit
def test_all_pass_results(clean_evidence):
    score = compute_score(clean_evidence)
    assert score == 100
    final_score, decision = decide(score, clean_evidence, [])
    assert final_score == 100
    assert decision == "greenlight"

@pytest.mark.unit
def test_all_critical_results(critical_evidence):
    score = compute_score(critical_evidence)
    assert score < 100
    final_score, decision = decide(score, critical_evidence, [])
    assert decision == "blocked"

@pytest.mark.unit
def test_score_boundary():
    score, decision = decide(69, [], [])
    assert decision == "blocked"
    score, decision = decide(70, [], [])
    assert decision == "greenlight"

@pytest.mark.unit
def test_security_penalty():
    findings = [
        SecurityFinding(rule_id="R1", severity="warning", file="a.py", evidence="", remediation=""),
        SecurityFinding(rule_id="R2", severity="warning", file="b.py", evidence="", remediation="")
    ]
    score, decision = decide(100, [], findings)
    assert score == 84
    
    findings.extend([
        SecurityFinding(rule_id="R3", severity="warning", file="c.py", evidence="", remediation=""),
        SecurityFinding(rule_id="R4", severity="warning", file="d.py", evidence="", remediation=""),
        SecurityFinding(rule_id="R5", severity="warning", file="e.py", evidence="", remediation="")
    ])
    score, decision = decide(100, [], findings)
    assert score == 60
    
@pytest.mark.unit
def test_critical_security():
    findings = [
        SecurityFinding(rule_id="R1", severity="critical", file="a.py", evidence="", remediation="")
    ]
    score, decision = decide(100, [], findings)
    assert decision == "blocked"

@pytest.mark.unit
def test_verdict_playbook_logic():
    report = build_verdict([], [], repo="my-repo", head_sha="abc1234")
    assert report.decision == "greenlight"
    assert report.rollback_playbook is None
    
    findings = [SecurityFinding(rule_id="R1", severity="critical", file="a.py", evidence="", remediation="")]
    report = build_verdict([], findings, repo="my-repo", head_sha="abc1234")
    assert report.decision == "blocked"
    assert report.rollback_playbook is not None
    assert "abc1234" in report.rollback_playbook

@pytest.mark.unit
def test_risk_brief():
    evidence = [EvidenceResult(module="change_intelligence", status="warning", risk_score_modifier=20, findings=["A bad finding"], recommended_action="Fix it")]
    brief = build_risk_brief(evidence, [])
    assert "Change Intelligence" in brief
    assert "A bad finding" in brief
    assert "Fix it" in brief
