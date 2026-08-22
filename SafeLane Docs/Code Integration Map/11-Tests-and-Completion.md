# 11 — Tests and Completion

## New tests to add before switching to v2

```text
tests/unit/test_inputs.py
  - bounds diff/path sizes and removes null bytes

tests/unit/test_security_preflight.py
  - private key/token blocks
  - broad workflow permissions block
  - unsafe shell pipe and disabled TLS warn
  - prompt injection is marked as untrusted data
  - preflight failure cannot greenlight

tests/unit/test_legacy_adapter.py
  - every legacy agent maps to one v2 module
  - unknown legacy name fails clearly

tests/unit/test_v2_verdict.py
  - weights total one
  - score boundaries and critical overrides
  - security penalty cap

tests/unit/test_publisher.py
  - only v2 module labels are shown
  - table content is bounded/escaped
  - raw PR body/diff and shell commands never appear

tests/integration/test_v2_fabric.py
  - four modules run concurrently
  - timeout/failure produces conservative warning
  - safe fixture can greenlight
  - secret fixture blocks before optional model use
  - one publish attempt per head SHA
```

## Commands

Run from the repository root after each small completed task:

```powershell
pytest tests/unit -q
pytest tests/integration -q
pytest -q
```

Run deterministic and mocked tests even if Azure/Foundry credentials are unavailable.

## Per-task completion checklist

- [ ] Existing source inspected.
- [ ] New architecture name recorded.
- [ ] Action recorded: reuse, rename, refactor, wrap, or replace.
- [ ] Existing behaviour preserved or deliberate change documented.
- [ ] Untrusted inputs identified.
- [ ] Local fallback exists for optional cloud/model dependency.
- [ ] New/changed code returns typed results.
- [ ] Relevant unit tests pass.
- [ ] Relevant integration tests pass.
- [ ] No secrets, raw diffs, or private data are logged.
- [ ] Rollback path and next task are recorded.

## Final definition of done

SafeLane v2 is ready only when a real or fixture PR reaches the Fabric, all four v2 module names appear in fixed GitHub output, Security Preflight runs before optional AI, critical findings deterministically block, the setup platform still works, the Incident Memory mock fallback works, and the full suite passes without Microsoft Foundry.
