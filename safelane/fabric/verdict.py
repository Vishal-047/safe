import logging
from safelane.contracts import EvidenceResult, SecurityFinding, VerdictReport, MODULE_WEIGHTS

logger = logging.getLogger('safelane.verdict')

def compute_score(evidence: list[EvidenceResult]) -> int:
    """Compute base score: 100 - sum(modifier * weight), clamped 0-100."""
    weighted_sum = sum(
        r.risk_score_modifier * MODULE_WEIGHTS.get(r.module, 0.25)
        for r in evidence
    )
    return int(max(0, min(100, 100 - weighted_sum)))

def decide(score: int, evidence: list[EvidenceResult], security_findings: list[SecurityFinding]) -> tuple[int, str]:
    """Apply security penalties and determine decision."""
    SECURITY_PENALTIES = {"info": 0, "warning": 8, "critical": 25}
    penalty = min(40, sum(SECURITY_PENALTIES.get(f.severity, 0) for f in security_findings))
    final_score = max(0, score - penalty)
    
    has_critical_evidence = any(r.status == "critical" for r in evidence)
    has_critical_security = any(f.severity == "critical" for f in security_findings)
    
    blocked = final_score < 70 or has_critical_evidence or has_critical_security
    
    return final_score, "blocked" if blocked else "greenlight"

def build_risk_brief(evidence: list[EvidenceResult], security_findings: list[SecurityFinding]) -> str:
    """Build a markdown risk brief from evidence and security findings."""
    lines = ["# SafeLane Risk Brief\n"]
    
    for r in evidence:
        lines.append(f"## {r.label} Module - Status: {r.status.upper()}")
        if r.findings:
            lines.append("### Findings:")
            for finding in r.findings:
                lines.append(f"- {finding}")
        if r.recommended_action:
            lines.append(f"**Recommendation:** {r.recommended_action}")
        lines.append("")
        
    if security_findings:
        lines.append("## Security Preflight Findings")
        for sf in security_findings:
            lines.append(f"- **{sf.severity.upper()}** [{sf.rule_id}] in {sf.file}: {sf.evidence}")
            if sf.remediation:
                lines.append(f"  *Remediation:* {sf.remediation}")
        lines.append("")
        
    return "\n".join(lines).strip()

def build_rollback_playbook(evidence: list[EvidenceResult], repo: str, head_sha: str | None) -> str | None:
    """Build a rollback playbook with concrete git revert steps. Only when blocked."""
    if not head_sha:
        return "Cannot build rollback playbook: HEAD SHA not provided."
        
    lines = [
        f"### Rollback Playbook for {repo}",
        "The current PR introduces critical risks or policy violations.",
        "To rollback the problematic changes safely, run the following commands:",
        "```bash",
        f"git fetch origin",
        f"git checkout -b revert-risky-changes-{head_sha[:7]}",
        f"git revert --no-commit {head_sha}..HEAD",
        "git commit -m 'Revert risky changes identified by SafeLane'",
        f"git push origin revert-risky-changes-{head_sha[:7]}",
        "```",
        "After pushing, please verify that the deployment is stable and create a new PR for these changes."
    ]
    return "\n".join(lines)

def build_verdict(evidence: list[EvidenceResult], security_findings: list[SecurityFinding], repo: str, head_sha: str | None = None) -> VerdictReport:
    """Full verdict pipeline: score -> decide -> brief -> playbook -> VerdictReport."""
    base_score = compute_score(evidence)
    final_score, decision = decide(base_score, evidence, security_findings)
    
    risk_brief = build_risk_brief(evidence, security_findings)
    
    rollback_playbook = None
    if decision == "blocked":
        rollback_playbook = build_rollback_playbook(evidence, repo, head_sha)
        
    return VerdictReport(
        confidence_score=final_score,
        decision=decision,
        risk_brief=risk_brief,
        rollback_playbook=rollback_playbook,
        evidence_results=evidence,
        security_findings=security_findings
    )
