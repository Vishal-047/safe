"""
SafeLane — Shared Data Contracts

Single source of truth for all typed shapes passed through the pipeline.
Do not duplicate these shapes elsewhere.

Architecture name mapping:
    Change Intelligence     → change_intelligence
    Incident Memory         → incident_memory
    Verification Readiness  → verification_readiness
    Release Context         → release_context
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ── Evidence Module identifiers ──────────────────────────────

EvidenceModule = Literal[
    "change_intelligence",
    "incident_memory",
    "verification_readiness",
    "release_context",
]

MODULE_LABELS: dict[str, str] = {
    "change_intelligence": "Change Intelligence",
    "incident_memory": "Incident Memory",
    "verification_readiness": "Verification Readiness",
    "release_context": "Release Context",
}

MODULE_WEIGHTS: dict[str, float] = {
    "change_intelligence": 0.30,
    "incident_memory": 0.25,
    "verification_readiness": 0.25,
    "release_context": 0.20,
}


# ── Evidence result (every evidence module returns exactly this) ──

class EvidenceResult(BaseModel):
    """Standardized result from any evidence module."""

    module: EvidenceModule
    status: Literal["pass", "warning", "critical"]
    risk_score_modifier: int = Field(ge=0, le=100)
    findings: list[str] = Field(default_factory=list)
    recommended_action: str

    @property
    def label(self) -> str:
        """Human-readable display name for this module."""
        return MODULE_LABELS[self.module]


# ── Security Preflight finding ───────────────────────────────

class SecurityFinding(BaseModel):
    """A single finding from the deterministic Security Preflight scan."""

    rule_id: str
    severity: Literal["info", "warning", "critical"]
    file: str | None = None
    evidence: str  # short, specific — never echoes a raw secret value
    remediation: str


# ── PR payload (normalized input to the Fabric Controller) ───

class PRPayload(BaseModel):
    """Normalized pull-request data flowing through the pipeline."""

    pr_number: int
    repo: str  # "owner/repo"
    changed_files: list[str] = Field(default_factory=list)
    diff: str = ""
    timestamp: datetime | None = None
    head_sha: str | None = None
    skip_autofix: bool = False


# ── Analysis request (what evidence modules receive) ─────────

class AnalysisRequest(BaseModel):
    """Derived from PRPayload — the shape evidence modules consume."""

    pr_number: int
    repository: str  # "owner/repo"
    changed_files: list[str] = Field(default_factory=list)
    diff: str = ""
    received_at: datetime | None = None
    head_sha: str | None = None
    skip_autofix: bool = False

    @classmethod
    def from_pr_payload(cls, payload: PRPayload) -> "AnalysisRequest":
        return cls(
            pr_number=payload.pr_number,
            repository=payload.repo,
            changed_files=payload.changed_files,
            diff=payload.diff,
            received_at=payload.timestamp,
            head_sha=payload.head_sha,
            skip_autofix=payload.skip_autofix,
        )


# ── Repository context (per-registration credentials/config) ─

class RepoContext(BaseModel):
    """Per-registration credentials and config that flow through the pipeline."""

    registration_id: str | None = None
    owner: str = ""
    repo: str = ""
    gh_token: str | None = None  # decrypted PAT, in-memory only
    azure_search_endpoint: str | None = None
    azure_search_key: str | None = None
    azure_tenant_id: str | None = None
    azure_workspace_id: str | None = None
    azure_customer_id: str | None = None
    azure_search_index: str | None = None


# ── Verdict report (final output of the pipeline) ────────────

class VerdictReport(BaseModel):
    """
    Final pipeline output. Enforced invariants via model_validator:
      - Any critical EvidenceResult → decision must be 'blocked'.
      - confidence_score < 70 → decision must be 'blocked'.
      - decision == 'greenlight' → rollback_playbook must be None.
    """

    confidence_score: int = Field(ge=0, le=100)
    decision: Literal["greenlight", "blocked"]
    risk_brief: str
    rollback_playbook: str | None = None
    evidence_results: list[EvidenceResult] = Field(default_factory=list)
    security_findings: list[SecurityFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_invariants(self) -> "VerdictReport":
        has_critical_evidence = any(
            r.status == "critical" for r in self.evidence_results
        )
        has_critical_security = any(
            f.severity == "critical" for f in self.security_findings
        )

        # Any critical finding forces blocked
        if has_critical_evidence or has_critical_security:
            if self.decision != "blocked":
                raise ValueError(
                    "A critical evidence or security finding requires decision='blocked'"
                )

        # Low score forces blocked
        if self.confidence_score < 70:
            if self.decision != "blocked":
                raise ValueError(
                    "confidence_score < 70 requires decision='blocked'"
                )

        # Greenlight must not carry a rollback playbook
        if self.decision == "greenlight" and self.rollback_playbook is not None:
            raise ValueError(
                "decision='greenlight' must have rollback_playbook=None"
            )

        return self
