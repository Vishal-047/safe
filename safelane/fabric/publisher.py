import logging
import asyncio
import httpx
from typing import Optional, List

from safelane.contracts import VerdictReport, MODULE_LABELS

logger = logging.getLogger('safelane.publisher')

def table_cell(value: str, limit: int = 160) -> str:
    """Sanitize a value for use in a markdown table cell."""
    if not value:
        return ""
    sanitized = " ".join(value.replace("|", "\\|").split())
    return sanitized[:limit]

def render_comment(report: VerdictReport) -> str:
    """Build a fixed-template PR comment from a VerdictReport."""
    
    decision_display = "GREENLIGHT ✅" if report.decision == "greenlight" else "BLOCKED 🚫"
    
    lines = [
        "## 🛡️ SafeLane Change Assurance Report",
        f"**Score:** {report.confidence_score}/100 — {decision_display}",
        "",
        "| Evidence Module | Status | Risk | Key Finding |",
        "|---|---|---:|---|"
    ]
    
    for er in report.evidence_results:
        mod_name = MODULE_LABELS.get(er.module, er.module)
        status = er.status
        risk = str(er.risk_score_modifier)
        finding = table_cell(er.findings[0] if er.findings else "No issues found")
        lines.append(f"| {mod_name} | {status} | {risk} | {finding} |")
        
    lines.extend([
        "",
        "<details><summary>📋 Risk Brief</summary>",
        report.risk_brief,
        "</details>"
    ])
    
    if "BLOCKED" in report.decision.upper() and report.rollback_playbook:
        lines.extend([
            "",
            "<details><summary>🔄 Rollback Playbook</summary>",
            report.rollback_playbook,
            "</details>"
        ])
        
    return "\n".join(lines)

def render_copilot_nudge(missing_tests: List[str], repo: str, pr_number: int) -> Optional[str]:
    """Build a fixed-template @copilot comment for missing tests."""
    if not missing_tests:
        return None
    files_str = "\n".join(f"- `{f}`" for f in missing_tests)
    return (
        f"@copilot Please generate unit tests for the following files modified in this PR:\n"
        f"{files_str}\n\n"
        "Ensure they cover edge cases and match our testing framework."
    )

async def post_pr_comment(repo: str, pr_number: int, body: str, token: str) -> bool:
    """POST a comment to a GitHub PR. Returns True on success."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            try:
                response = await client.post(url, headers=headers, json={"body": body})
                if response.status_code == 201:
                    return True
                logger.warning(f"Failed to post comment. Status: {response.status_code}, Body: {response.text}")
            except Exception as e:
                logger.warning(f"Exception posting comment (attempt {attempt+1}/3): {e}")
            await asyncio.sleep(2 ** attempt)
            
    logger.error("Final failure posting PR comment.")
    return False

async def publish_verdict(report: VerdictReport, repo: str, pr_number: int, token: Optional[str]) -> bool:
    """Render and post the full verdict comment. Optionally post copilot nudge."""
    if not token:
        logger.warning("No GitHub token provided, skipping comment publication.")
        return False
        
    comment_body = render_comment(report)
    success = await post_pr_comment(repo, pr_number, comment_body, token)
    
    if "BLOCKED" in report.decision.upper():
        # Look for missing tests in verification_readiness
        missing_tests = []
        for er in report.evidence_results:
            if er.module == "verification_readiness" and er.status != "pass":
                # Simplistic extraction for MVP
                for f in er.findings:
                    if "missing test" in f.lower():
                        parts = f.split(" ")
                        for p in parts:
                            if "." in p and not p.endswith("."):
                                missing_tests.append(p)
                                
        if missing_tests:
            nudge = render_copilot_nudge(missing_tests, repo, pr_number)
            if nudge:
                await post_pr_comment(repo, pr_number, nudge, token)
                
    return success
