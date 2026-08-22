# 03 — Contracts and Security

## Purpose

Add v2 names and Security Preflight without breaking current `AgentResult` callers. Keep the legacy contract until the controller, API output, and tests have migrated.

## New file: `safelane/contracts.py`

```python
from typing import Literal

from pydantic import BaseModel, Field

EvidenceModule = Literal[
    "change_intelligence", "incident_memory",
    "verification_readiness", "release_context",
]

MODULE_LABELS = {
    "change_intelligence": "Change Intelligence",
    "incident_memory": "Incident Memory",
    "verification_readiness": "Verification Readiness",
    "release_context": "Release Context",
}


class EvidenceResult(BaseModel):
    module: EvidenceModule
    status: Literal["pass", "warning", "critical"]
    risk_score_modifier: int = Field(ge=0, le=100)
    findings: list[str] = Field(default_factory=list, max_length=8)
    recommended_action: str

    @property
    def label(self) -> str:
        return MODULE_LABELS[self.module]


class SecurityFinding(BaseModel):
    rule_id: str
    severity: Literal["info", "warning", "critical"]
    evidence: str
    remediation: str
```

## Legacy adapter

**New file:** `safelane/evidence/legacy_adapter.py`

```python
from agents.shared.data_contract import AgentResult
from safelane.contracts import EvidenceResult

LEGACY_MODULES = {
    "Diff Analyst": "change_intelligence",
    "History Agent": "incident_memory",
    "Coverage Agent": "verification_readiness",
    "Timing Agent": "release_context",
}


def adapt_legacy_result(result: AgentResult) -> EvidenceResult:
    return EvidenceResult(
        module=LEGACY_MODULES[result.agent_name],
        status=result.status,
        risk_score_modifier=result.risk_score_modifier,
        findings=result.findings[:8],
        recommended_action=result.recommended_action,
    )
```

## Input normalizer

Create `safelane/fabric/inputs.py`. It must normalize Unicode, remove null bytes, cap input length, and preserve PR content strictly as data. Never inject PR prose directly into an LLM system instruction.

```python
import unicodedata

MAX_DIFF_CHARS = 200_000


def clean_untrusted_text(value: str, limit: int) -> str:
    return unicodedata.normalize("NFKC", value or "").replace("\x00", "")[:limit]
```

## Security Preflight

Create `safelane/fabric/security_preflight.py`. It runs before every evidence module and uses deterministic rules only.

Minimum rules:

- Private-key block or token-like string: `critical`.
- GitHub workflow `permissions: write-all`: `critical`.
- `curl | sh` or `wget | bash`: `warning`.
- `verify=False` or `--no-check-certificate`: `warning`.
- Prompt-injection pattern in PR text/diff: `warning`; never execute it.

## Before continuing

- [ ] Each old agent maps to exactly one v2 module.
- [ ] An unknown old name throws a clear error.
- [ ] Security rules have safe and unsafe unit fixtures.
- [ ] A preflight failure produces a conservative warning, never an implicit pass.
