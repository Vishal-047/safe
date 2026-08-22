import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger('safelane.incident_memory')

@dataclass
class IncidentRecord:
    id: str
    title: str
    severity: str
    affected_files: List[str]
    timestamp: str
    summary: str

def get_mock_incidents() -> List[IncidentRecord]:
    return [
        IncidentRecord(
            id="INC-101",
            title="Payment processing failure",
            severity="critical",
            affected_files=["src/payment/processor.py"],
            timestamp="2024-01-15T10:00:00Z",
            summary="Payment processing failed due to race condition."
        ),
        IncidentRecord(
            id="INC-102",
            title="Authentication timeout",
            severity="warning",
            affected_files=["src/auth/middleware.py"],
            timestamp="2024-02-20T14:30:00Z",
            summary="Users experienced timeouts during login."
        ),
        IncidentRecord(
            id="INC-103",
            title="Cache invalidation bug",
            severity="warning",
            affected_files=["src/cache/redis_store.py", "utils.py"],
            timestamp="2024-03-05T09:15:00Z",
            summary="Stale data served due to bad invalidation logic."
        )
    ]

def search_incidents(changed_files: List[str], endpoint: str, key: str, index_name: str) -> List[IncidentRecord]:
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
    except ImportError:
        logger.warning("azure-search-documents not installed.")
        raise RuntimeError("Azure SDK not installed - incident search unavailable.")

    credential = AzureKeyCredential(key)
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    
    matched_incidents = []
    seen_ids = set()
    
    for f in changed_files:
        import os
        basename = os.path.basename(f)
        stem = os.path.splitext(basename)[0]
        search_text = f'"{f}" OR "{basename}" OR "{stem}"'
        
        results = client.search(search_text=search_text)
        for r in results:
            inc_id = r.get("id")
            if inc_id not in seen_ids:
                seen_ids.add(inc_id)
                matched_incidents.append(IncidentRecord(
                    id=inc_id or "Unknown",
                    title=r.get("title", "Unknown"),
                    severity=r.get("severity", "info"),
                    affected_files=r.get("affected_files", []),
                    timestamp=r.get("timestamp", ""),
                    summary=r.get("summary", "")
                ))
    
    matched_incidents.sort(key=lambda x: x.timestamp, reverse=True)
    return matched_incidents
