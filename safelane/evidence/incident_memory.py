import asyncio
import logging
import re
from pathlib import Path

from safelane.contracts import AnalysisRequest, RepoContext, EvidenceResult, SecurityFinding
from safelane.evidence.incident_store import search_incidents, get_mock_incidents

logger = logging.getLogger('safelane.incident_memory')

def derive_index_name(owner: str, repo: str) -> str:
    name = f"{owner}-{repo}".lower()
    return re.sub(r'[^a-z0-9\-]', '-', name)

def _match_incident_to_files(changed_files: list[str], mock_incidents: list) -> list:
    matched = []
    seen = set()
    for incident in mock_incidents:
        for f in changed_files:
            p = Path(f)
            basename = p.name
            stem = p.stem
            
            for af in incident.affected_files:
                af_p = Path(af)
                if f == af or basename == af_p.name or stem == af_p.stem:
                    if incident.id not in seen:
                        seen.add(incident.id)
                        matched.append(incident)
    matched.sort(key=lambda x: x.timestamp, reverse=True)
    return matched

async def run(request: AnalysisRequest, repo_context: RepoContext | None = None) -> EvidenceResult:
    if not repo_context or not repo_context.azure_search_endpoint or not repo_context.azure_search_key:
        return EvidenceResult(
            module="incident_memory",
            status="pass",
            risk_score_modifier=0,
            findings=["No deployment connection — no relevant incident history available."],
            recommended_action="Continue without incident history"
        )
    
    index_name = derive_index_name(repo_context.owner, repo_context.repo)
    
    try:
        if repo_context.azure_search_endpoint == "mock":
            mock_incidents = get_mock_incidents()
            incidents = _match_incident_to_files(request.changed_files, mock_incidents)
        else:
            incidents = await asyncio.to_thread(
                search_incidents,
                request.changed_files,
                repo_context.azure_search_endpoint,
                repo_context.azure_search_key,
                index_name
            )
    except Exception as e:
        logger.warning(f"Incident search temporarily unavailable: {e}")
        return EvidenceResult(
            module="incident_memory",
            status="warning",
            risk_score_modifier=10,
            findings=["Incident search temporarily unavailable"],
            recommended_action="Review manually if critical files are touched."
        )
    
    if not incidents:
        return EvidenceResult(
            module="incident_memory",
            status="pass",
            risk_score_modifier=0,
            findings=[],
            recommended_action=""
        )
    
    findings = []
    has_critical = False
    
    for inc in incidents:
        if inc.severity == "critical":
            has_critical = True
        findings.append(f"PREVIOUS_INCIDENT_{inc.id} ({inc.severity}): {inc.title} - {inc.summary}")
    
    if len(incidents) >= 3 or has_critical:
        status = "critical"
        risk_score_modifier = 60
    else:
        status = "warning"
        risk_score_modifier = 30
        
    return EvidenceResult(
        module="incident_memory",
        status=status,
        risk_score_modifier=risk_score_modifier,
        findings=findings,
        recommended_action="Review related incidents carefully before approving."
    )
