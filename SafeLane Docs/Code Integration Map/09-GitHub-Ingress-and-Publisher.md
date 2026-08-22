# 09 — GitHub Ingress and Publisher

## Source and v2 action

| Item | Value |
|---|---|
| Existing source | `agents/orchestrator/server.py` |
| New architecture name | GitHub Ingress; Fixed-template GitHub Publisher |
| Action | Refactor |
| Risk | High: this is the public webhook and PR output path. |
| Tests | `tests/unit/test_server.py`, `tests/integration/test_e2e_server.py` |

## Preserve

- HMAC-SHA256 signature verification.
- Handling only `pull_request` opened, synchronize, and reopened events.
- Registration lookup before analysis.
- Changed-file pagination and diff retrieval.
- `202 Accepted` response before background work.

## Fixed publisher requirement

Render output from typed evidence. Never publish raw diff, PR body, model-authored commands, or unsanitized table content.

```python
def table_cell(value: str, limit: int = 160) -> str:
    return " ".join(value.replace("|", "\\|").split())[:limit]


def render_comment(report) -> str:
    lines = [
        "## SafeLane Change Assurance",
        f"**Decision:** `{report.decision.upper()}` | **Confidence:** `{report.confidence_score}/100`",
        "",
        "| Evidence module | Status | Risk | Key finding |",
        "|---|---|---:|---|",
    ]
    for item in report.evidence:
        finding = item.findings[0] if item.findings else "No finding provided."
        lines.append(
            f"| {item.label} | {item.status} | {item.risk_score_modifier} | {table_cell(finding)} |"
        )
    return "\n".join(lines)
```

## Webhook change rule

Use FastAPI `BackgroundTasks` only for the hackathon/single-process flow. It gives a fast `202` response, but it is not a durable queue. Before production, persist an analysis run keyed by repository, PR number, and head SHA to prevent duplicate GitHub retries from duplicating analysis/comments.

## Checklist

- [ ] Invalid HMAC returns `401`.
- [ ] Ignored event/actions return safely without analysis.
- [ ] Registered PR returns `202`.
- [ ] PR text with pipes/newlines cannot break the Markdown table.
- [ ] Only one publisher owns PR comments; Verification Readiness cannot post a second comment.
