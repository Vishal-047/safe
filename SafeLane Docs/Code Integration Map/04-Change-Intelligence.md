# 04 — Change Intelligence

## Source and v2 action

| Item | Value |
|---|---|
| Existing source | `agents/diff_analyst/diff_agent.py` |
| New architecture name | Change Intelligence |
| Action | Rename and refactor |
| Risk | Medium-high: existing security heuristics and fallback behaviour must remain reliable. |
| Tests | `tests/unit/test_diff_analyst.py`, `tests/integration/test_e2e_agents.py` |

## Preserve

- Deterministic checks for removed error handling, retry/backoff removal, and risky schema changes.
- Optional LLM analysis only as enrichment.
- Valid structured result and heuristic fallback when LLM configuration/output fails.

## Move out

Move exposed-secret and prompt-injection detection into Security Preflight. It must run before a model sees the diff.

## Safe first wrapper

**New file:** `safelane/evidence/change_intelligence.py`

```python
from agents.diff_analyst.diff_agent import run as run_legacy_diff
from agents.shared.data_contract import RepoContext
from safelane.contracts import AnalysisRequest, EvidenceResult
from safelane.evidence.legacy_adapter import adapt_legacy_result


async def run(
    request: AnalysisRequest,
    repo_context: RepoContext | None = None,
) -> EvidenceResult:
    del repo_context
    legacy = await run_legacy_diff(
        diff=request.diff,
        changed_files=request.changed_files,
    )
    return adapt_legacy_result(legacy)
```

## Later refactor rule

When moving the underlying code, keep the deterministic scanner as the source of truth. Model prompts must put diff text inside a clearly delimited data block and demand JSON matching `EvidenceResult`; a model may not downgrade a deterministic warning or critical finding.

## Checklist

- [ ] Empty diff returns a warning, not an error.
- [ ] Removed retry/error handling and schema change still produce the current risk signal.
- [ ] Secret fixture blocks through Security Preflight before any model call.
- [ ] Invalid model JSON uses deterministic fallback.
