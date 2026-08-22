import logging
import os
import asyncio
import re
from typing import Any

from safelane.contracts import AnalysisRequest, RepoContext, EvidenceResult

logger = logging.getLogger('safelane.change_intelligence')

ERROR_HANDLING_PATTERN = re.compile(r'(try:|except|catch|\.catch\(|on_error|rescue)', re.IGNORECASE)
RETRY_PATTERN = re.compile(r'(retry|backoff|timeout|Retry|with_retries|max_retries)', re.IGNORECASE)
SCHEMA_CHANGE_PATTERN = re.compile(r'(DROP TABLE|DROP COLUMN|ALTER COLUMN|TRUNCATE)', re.IGNORECASE)

def _reword_findings_with_llm(findings: list[str]) -> list[str]:
    """Call LLM to reword findings for readability. Synchronous."""
    if not findings:
        return findings

    try:
        from openai import AzureOpenAI
        # Simple client creation (assumes other env vars like AZURE_OPENAI_API_KEY might be set)
        client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version="2023-05-15",
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", "dummy"),
        )
        # Using a dummy deployment name or reading from env; fallback to a default
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        
        prompt = "Reword the following findings for better readability. Do not change the meaning. Return one per line.\n" + "\n".join(findings)
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        
        content = response.choices[0].message.content
        if content:
            new_findings = [line.strip("- *") for line in content.split("\n") if line.strip()]
            if len(new_findings) > 0:
                return new_findings
        return findings
    except Exception as e:
        logger.warning(f"LLM enrichment failed, falling back to heuristics: {e}")
        return findings

async def run(request: AnalysisRequest, repo_context: RepoContext | None = None) -> EvidenceResult:
    logger.info(f"Running Change Intelligence module for PR {request.pr_number}")
    
    findings = []
    
    if not request.diff or not request.diff.strip():
        return EvidenceResult(
            module="change_intelligence",
            status="warning",
            risk_score_modifier=20,
            findings=["no diff content"],
            recommended_action="Provide a valid diff for analysis."
        )
    
    lines = request.diff.splitlines()
    if len(lines) > 500:
        findings.append("Large change detected (>500 lines), increasing review complexity.")
        
    removed_error_handling = 0
    removed_retry = 0
    schema_drops = 0
    schema_alters = 0
    
    for line in lines:
        if line.startswith("-"):
            if ERROR_HANDLING_PATTERN.search(line):
                removed_error_handling += 1
            if RETRY_PATTERN.search(line):
                removed_retry += 1
        
        if line.startswith("+") or line.startswith("-"):
            if "DROP TABLE" in line.upper() or "DROP COLUMN" in line.upper() or "TRUNCATE" in line.upper():
                schema_drops += 1
            elif "ALTER COLUMN" in line.upper():
                schema_alters += 1
                
    if removed_error_handling > 0:
        findings.append(f"Removed error handling logic detected ({removed_error_handling} occurrences).")
    if removed_retry > 0:
        findings.append(f"Removed retry/backoff/timeout logic detected ({removed_retry} occurrences).")
    if schema_drops > 0:
        findings.append(f"Risky schema drops detected (DROP/TRUNCATE) ({schema_drops} occurrences).")
    if schema_alters > 0:
        findings.append(f"Schema modifications detected (ALTER) ({schema_alters} occurrences).")
        
    # Scoring Logic
    status = "pass"
    modifier = 0
    recommended_action = "Proceed with review."
    
    total_issues = (1 if removed_error_handling > 0 else 0) + \
                   (1 if removed_retry > 0 else 0) + \
                   (1 if schema_drops > 0 else 0) + \
                   (1 if schema_alters > 0 else 0)
                   
    is_large = len(lines) > 500
    
    if schema_drops > 0 or total_issues > 1:
        status = "critical"
        modifier = 60
        recommended_action = "Thoroughly review safety mechanisms and schema changes."
    elif total_issues == 1 or is_large:
        status = "warning"
        modifier = 30
        recommended_action = "Ensure removed safety logic is replaced or no longer needed."
    
    if findings and "AZURE_OPENAI_ENDPOINT" in os.environ:
        logger.info("Attempting LLM enrichment for findings.")
        try:
            enriched_findings = await asyncio.to_thread(_reword_findings_with_llm, findings)
            # LLM CANNOT change severity, score, or status
            findings = enriched_findings
        except Exception as e:
            logger.warning(f"Unexpected error during LLM enrichment: {e}")
        
    return EvidenceResult(
        module="change_intelligence",
        status=status,
        risk_score_modifier=modifier,
        findings=findings,
        recommended_action=recommended_action
    )
