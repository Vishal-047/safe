# 01 — Architecture and Migration

## SafeLane v2 architecture

```text
GitHub PR event
  -> GitHub Ingress
  -> SafeLane Change Assurance Fabric
       1. Input Normalizer and Trust Boundary
       2. Security Preflight
       3. Concurrent Evidence Modules
       4. Deterministic Verdict and Policy Layer
       5. Fixed-template GitHub Publisher
  -> GitHub PR comment / check result and audit record

Supporting services
  Setup Platform | Incident Memory Ingestion | Optional Foundry Adapter
```

## Required name mapping

| Existing name | v2 name |
|---|---|
| Diff Analyst | Change Intelligence |
| History Agent | Incident Memory |
| Coverage Agent | Verification Readiness |
| Timing Agent | Release Context |
| Verdict Agent | Deterministic Verdict and Policy Layer |
| Orchestrator | Change Assurance Fabric Controller |
| PR-comment helper | Fixed-template GitHub Publisher |

## Safe migration sequence

1. Add v2 contracts and adapters; do not change existing agents.
2. Add Input Normalizer and deterministic Security Preflight with unit tests.
3. Add the Fabric Controller, initially calling existing agents through wrappers.
4. Add deterministic verdict policy and fixed-template publisher.
5. Change the webhook behind a feature flag or small, reversible integration commit.
6. Update the setup workflow template.
7. Move individual module logic only after module-specific tests pass.
8. Delete legacy wrappers only after the full test suite and a GitHub smoke test pass.

## Non-negotiable policy

- Final scores and block/greenlight decisions are deterministic code.
- A model may improve wording only; it may not control permissions, merges, deployment, commands, or policy.
- A timeout, failed module, or failed Security Preflight cannot silently result in a greenlight.
- Keep Foundry optional and preserve a fully local fallback.
