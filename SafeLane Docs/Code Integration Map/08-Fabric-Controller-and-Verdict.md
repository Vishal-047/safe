# 08 — Fabric Controller and Verdict

## Source and v2 action

| Item | Value |
|---|---|
| Existing sources | `agents/orchestrator/__init__.py`, `agents/verdict_agent/__init__.py` |
| New architecture name | Change Assurance Fabric Controller; Deterministic Verdict and Policy Layer |
| Action | Refactor |
| Risk | High: this code determines whether a risky PR is blocked. |
| Tests | Orchestrator/Verdict unit tests and full pipeline integration tests |

## Controller rule

Run all four evidence modules concurrently. Each must have a bounded timeout. A timeout or exception becomes a warning evidence result with zero confidence, not a missing result.

```python
import asyncio

MODULE_TIMEOUT_SECONDS = 30


async def run_one(name, runner, request, repo_context):
    try:
        return await asyncio.wait_for(
            runner(request, repo_context), timeout=MODULE_TIMEOUT_SECONDS
        )
    except Exception as error:
        return EvidenceResult(
            module=name,
            status="warning",
            risk_score_modifier=50,
            findings=[f"{name} could not complete: {type(error).__name__}."],
            recommended_action="Perform manual review before merging.",
        )
```

## Verdict rule

Preserve the existing weights:

```python
WEIGHTS = {
    "change_intelligence": 0.30,
    "incident_memory": 0.25,
    "verification_readiness": 0.25,
    "release_context": 0.20,
}
SECURITY_PENALTIES = {"info": 0, "warning": 8, "critical": 25}
```

```python
def decide(evidence, security_findings):
    weighted_risk = sum(
        item.risk_score_modifier * WEIGHTS[item.module]
        for item in evidence
    )
    base_score = max(0, min(100, round(100 - weighted_risk)))
    penalty = min(40, sum(SECURITY_PENALTIES[f.severity] for f in security_findings))
    score = max(0, base_score - penalty)
    blocked = (
        score < 70
        or any(item.status == "critical" for item in evidence)
        or any(item.severity == "critical" for item in security_findings)
    )
    return score, "blocked" if blocked else "greenlight"
```

## Checklist

- [ ] Weights total `1.0`.
- [ ] Any critical evidence or security finding blocks.
- [ ] Security warning penalties are capped at 40 points.
- [ ] A 70 score greenlights only when there is no critical finding.
- [ ] No model call can change the calculated score or decision.
