# 06 — Verification Readiness

## Source and v2 action

| Item | Value |
|---|---|
| Existing source | `agents/coverage_agent/__init__.py` |
| New architecture name | Verification Readiness |
| Action | Refactor |
| Risk | Medium: this module currently posts a separate Copilot comment. |
| Tests | `tests/test_coverage_agent.py`, `tests/integration/test_e2e_agents.py` |

## Preserve

- Test-path inference.
- Detection of deleted test files and missing tests for changed Python files.
- GitHub API error fallback.
- Per-repository token passed through `RepoContext`.

## Required change

The evidence module must only return evidence. It must not post a Copilot-triggering comment. The Fixed-template GitHub Publisher becomes the sole owner of PR comments, preventing duplicate or model-directed output.

## Safe first wrapper

**New file:** `safelane/evidence/verification_readiness.py`

```python
from agents.coverage_agent import run as run_legacy_coverage
from agents.shared.data_contract import RepoContext
from safelane.contracts import AnalysisRequest, EvidenceResult
from safelane.evidence.legacy_adapter import adapt_legacy_result


async def run(request: AnalysisRequest, repo_context: RepoContext | None) -> EvidenceResult:
    token = repo_context.gh_token if repo_context else None
    legacy = await run_legacy_coverage(
        pr_number=request.pr_number,
        repo=request.repository,
        gh_token=token,
        skip_autofix=True,
    )
    return adapt_legacy_result(legacy)
```

## Checklist

- [ ] Missing test produces an evidence finding.
- [ ] Removed test produces an evidence finding.
- [ ] `skip_autofix=True` prevents an additional PR comment.
- [ ] GitHub failure produces a warning result with a manual-review action.
