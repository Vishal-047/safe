import asyncio
import logging
from typing import List

from safelane.contracts import (
    AnalysisRequest, RepoContext, EvidenceResult, VerdictReport, PRPayload,
    MODULE_LABELS, MODULE_WEIGHTS, SecurityFinding
)
from safelane.fabric.inputs import clean_untrusted_text, normalize_pr_payload
from safelane.fabric.security_preflight import run_preflight, apply_security_policy

# Evidence modules
from safelane.evidence import change_intelligence, incident_memory, verification_readiness, release_context

def build_verdict(request: AnalysisRequest, evidence_results: List[EvidenceResult], security_findings: list[SecurityFinding]) -> VerdictReport:
    """Dynamic verdict builder evaluating security preflight findings and evidence modules."""
    # 1. Apply security policy
    final_score, has_security_blocker = apply_security_policy(100, security_findings)
    
    # 2. Populate change_intelligence findings if security findings exist
    security_findings_list = [f.evidence for f in security_findings]
    if security_findings:
        for idx, er in enumerate(evidence_results):
            if er.module == "change_intelligence":
                status = "critical" if has_security_blocker else ("warning" if security_findings else er.status)
                risk_mod = 50 if has_security_blocker else 25
                evidence_results[idx] = EvidenceResult(
                    module="change_intelligence",
                    status=status,
                    risk_score_modifier=risk_mod,
                    findings=security_findings_list,
                    recommended_action="Remediate exposed secrets or dangerous code execution patterns immediately."
                )

    # 3. Compute score and block decision
    total_evidence_risk = sum(er.risk_score_modifier for er in evidence_results if er.status != "pass")
    confidence_score = max(0, min(100, final_score - (total_evidence_risk // 2)))
    
    is_blocked = has_security_blocker or any(er.status == "critical" for er in evidence_results) or confidence_score < 60
    decision = "blocked" if is_blocked else "greenlight"
    
    # 4. Generate dynamic Markdown risk brief
    brief_lines = []
    if security_findings:
        brief_lines.append("### 🚨 Security Vulnerabilities Detected:")
        for sf in security_findings:
            icon = "🔴" if sf.severity == "critical" else "⚠️"
            brief_lines.append(f"- {icon} **[{sf.severity.upper()}]** {sf.evidence} — *Remediation:* {sf.remediation}")
        brief_lines.append("")
        
    for er in evidence_results:
        if er.status != "pass" and er.findings and er.module != "change_intelligence":
            brief_lines.append(f"### 🔍 {MODULE_LABELS.get(er.module, er.module)} ({er.status.upper()}):")
            for f in er.findings:
                brief_lines.append(f"- {f}")
            if er.recommended_action:
                brief_lines.append(f"  *Action:* {er.recommended_action}")
            brief_lines.append("")
            
    if not brief_lines:
        brief_lines.append("✅ **All security checks and evidence modules passed with 0 detected risks.**")
        
    risk_brief = "\n".join(brief_lines)
    
    # 5. Playbook if blocked
    playbook = None
    if is_blocked:
        playbook = (
            "1. **Revert changes:** `git revert HEAD` to pull back dangerous secrets or unsafe commands.\n"
            "2. **Secret Rotation:** If secrets were exposed, invalidate/rotate them immediately in cloud provider dashboards.\n"
            "3. **Code Review:** Replace `eval()` or `exec()` with safe static function calls before re-submitting PR."
        )
        
    return VerdictReport(
        confidence_score=confidence_score,
        decision=decision,
        risk_brief=risk_brief,
        rollback_playbook=playbook,
        evidence_results=evidence_results,
        security_findings=security_findings
    )

logger = logging.getLogger('safelane.controller')

MODULE_TIMEOUT_SECONDS = 30

async def run_module(name: str, runner, request: AnalysisRequest, repo_context: RepoContext | None) -> EvidenceResult:
    """Run a single evidence module with timeout and fallback."""
    try:
        return await asyncio.wait_for(
            runner(request, repo_context),
            timeout=MODULE_TIMEOUT_SECONDS
        )
    except Exception as error:
        logger.warning(f"{name} failed: {type(error).__name__}: {error}")
        return EvidenceResult(
            module=name,
            status="warning",
            risk_score_modifier=50,
            findings=[f"{MODULE_LABELS.get(name, name)} could not complete: {type(error).__name__}."],
            recommended_action="Perform manual review before merging.",
        )

async def orchestrate(payload: PRPayload, repo_context: RepoContext | None = None) -> VerdictReport:
    """Full SafeLane pipeline: normalize → preflight → evidence → verdict."""
    # 1. Build AnalysisRequest from PRPayload
    request = AnalysisRequest.from_pr_payload(payload)
    
    # 2. Run Security Preflight (deterministic, before evidence)
    security_findings = run_preflight(
        diff=request.diff,
        changed_files=request.changed_files,
    )
    
    # 3. Dispatch all four Evidence Modules concurrently
    modules = [
        ("change_intelligence", change_intelligence.run),
        ("incident_memory", incident_memory.run),
        ("verification_readiness", verification_readiness.run),
        ("release_context", release_context.run),
    ]
    
    evidence_results = await asyncio.gather(*[
        run_module(name, runner, request, repo_context)
        for name, runner in modules
    ])
    
    # 4. Build verdict
    verdict_report = build_verdict(request, list(evidence_results), security_findings)
    
    return verdict_report
