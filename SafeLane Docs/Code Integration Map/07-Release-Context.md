# 07 — Release Context

## Source and v2 action

| Item | Value |
|---|---|
| Existing source | `agents/timing_agent/__init__.py` |
| New architecture name | Release Context |
| Action | Rename and refactor |
| Risk | Low-medium: isolated, deterministic logic. |
| Tests | `tests/unit/test_timing_agent.py`, `tests/integration/test_e2e_agents.py` |

## Preserve

- Timezone-aware timestamps.
- Day, time-of-day, holiday, and release-proximity scores.
- Score cap and deterministic status mapping.
- No-network behaviour.

## Safe first wrapper

**New file:** `safelane/evidence/release_context.py`

```python
from agents.shared.data_contract import RepoContext
from agents.timing_agent import run as run_legacy_timing
from safelane.contracts import AnalysisRequest, EvidenceResult
from safelane.evidence.legacy_adapter import adapt_legacy_result


async def run(
    request: AnalysisRequest,
    repo_context: RepoContext | None = None,
) -> EvidenceResult:
    del repo_context
    legacy = await run_legacy_timing(deploy_timestamp=request.received_at)
    return adapt_legacy_result(legacy)
```

## Later improvement

The current calendar is US federal holidays. Do not silently replace it with another locale. Add a repository-level `release_region` configuration only after a documented product decision and tests for each calendar.

## Checklist

- [ ] Friday evening remains critical.
- [ ] Core Tuesday–Thursday hours remain low risk.
- [ ] Naive dates become timezone-aware predictably.
- [ ] Release-date proximity remains tested.
