# 05 — Incident Memory

## Source and v2 action

| Item | Value |
|---|---|
| Existing sources | `agents/history_agent/agent.py`, `mcp_servers/azure_mcp_server/` |
| New architecture name | Incident Memory |
| Action | Rename and wrap |
| Risk | Medium: per-repository credentials and Azure availability affect results. |
| Tests | `tests/unit/test_history_agent.py`, `tests/integration/test_e2e_agents.py` |

## Preserve

- Exact path/basename matching that prevents unrelated-file false positives.
- Most-recent incident ordering and existing risk thresholds.
- `RepoContext` so one repository cannot query another repository’s incident data.
- Mock incidents and warning behaviour when no incident connection exists.

## First wrapper

**New file:** `safelane/evidence/incident_memory.py`

```python
from agents.history_agent.agent import run as run_legacy_history
from agents.shared.data_contract import RepoContext
from safelane.contracts import AnalysisRequest, EvidenceResult
from safelane.evidence.legacy_adapter import adapt_legacy_result


async def run(
    request: AnalysisRequest,
    repo_context: RepoContext | None,
) -> EvidenceResult:
    legacy = await run_legacy_history(
        changed_files=request.changed_files,
        repo_ctx=repo_context,
    )
    return adapt_legacy_result(legacy)
```

## Integration notes

- Azure AI Search is an **optional incident store**, not a requirement for a valid local demo.
- Keep Azure SDK code inside `mcp_servers/azure_mcp_server/` or a narrow adapter; do not import it from the verdict layer.
- The Azure Function in `function_deploy/` is an ingestion path. It should not run during a PR analysis.

## Checklist

- [ ] An unrelated filename does not trigger an incident result.
- [ ] Missing Azure connection returns a clear warning/pass policy already covered by tests, not a crash.
- [ ] Mock data supports demo and test flows without Azure credentials.
