# 02 — Repository Integration Map

Use this matrix before editing an existing file. Each row states the **new architecture name**, required action, integration guidance, risk, and tests.

| Existing source | New architecture name | Action | Integration notes | Risk | Required tests before changing |
|---|---|---|---|---|---|
| `agents/shared/data_contract.py` | v2 Contracts | Wrap, then refactor | Add `safelane/contracts.py` first; preserve legacy Pydantic contracts until callers move. | High | `test_orchestrator.py`, `test_verdict_agent.py`, E2E pipeline |
| `agents/orchestrator/__init__.py` | Change Assurance Fabric Controller | Refactor | Preserve concurrent execution, 30-second timeouts, fallbacks, and all weights. | High | Orchestrator unit + pipeline integration tests |
| `agents/orchestrator/server.py` | GitHub Ingress / Publisher adapter | Refactor | Keep HMAC, event filtering, pagination, registration lookup, and `202`. | High | Server unit + E2E server tests |
| `agents/diff_analyst/diff_agent.py` | Change Intelligence | Rename and refactor | Keep change-risk heuristics and safe fallback; move secrets/injection to preflight. | Medium-high | Diff Analyst unit + E2E agent tests |
| `agents/history_agent/agent.py` | Incident Memory | Rename and wrap | Preserve file matching, incident ordering, mock fallback, and `RepoContext`. | Medium | History unit + E2E agent tests |
| `mcp_servers/azure_mcp_server/` | Incident Memory store and ingestion adapter | Reuse and wrap | Keep Azure SDK details outside controller/verdict code. | Medium | Mocked Azure pipeline tests + search smoke test |
| `function_deploy/function_app.py` | Incident Memory ingestion deployment | Reuse | Retain timer, Event Grid, and HTTP triggers as support paths. | Medium | Function smoke + ingestion test |
| `agents/coverage_agent/__init__.py` | Verification Readiness | Refactor | Keep test-path checks; disable current Copilot comment side effect. | Medium | `test_coverage_agent.py` + E2E agent tests |
| `agents/timing_agent/__init__.py` | Release Context | Rename and refactor | Keep timezone/risk logic; regional calendars need a later product decision. | Low-medium | Timing unit + E2E agent tests |
| `agents/verdict_agent/__init__.py` | Deterministic Verdict and Policy Layer | Refactor | Preserve weighting and critical override; add Security Preflight policy. | High | Verdict unit + pipeline tests |
| `foundry/deployment_config/` | Optional Foundry Adapter | Wrap | Retain tracing and optional narration; never require it for v2 decisions. | Medium | Foundry unit tests |
| `platform/server/` | Setup Platform | Reuse | Keep independent of Fabric internals; it knows the orchestrator only by URL. | Medium | Platform route/OAuth smoke tests |
| `platform/server/services/github_service.py` | Workflow Installer | Refactor carefully | Update workflow only after validating least permissions in a disposable repo. | High | Workflow renderer test + disposable-repo smoke test |
| `platform/server/services/db.py` | Registration store / future run store | Refactor carefully | Reuse registration and encrypted PAT fields; add runs later for durable idempotency. | High | DB init and registration tests |
| `requirements.txt`, `platform/requirements.txt`, `pyproject.toml` | v2 dependency manifest | Reuse, consolidate later | No paid dependency is needed for preflight. Keep cloud dependencies optional where possible. | Medium | Clean virtual-env installation + full tests |
| `tests/` | v2 regression/backtest suite | Extend | Rename test descriptions gradually; never delete existing coverage just because names changed. | High | Entire suite |
| `vscode_extension/` | Out of v2 scope | Leave unchanged | Do not delete it in this migration. | Low if untouched | None while unchanged |

## Target folders

```text
safelane/
  contracts.py
  evidence/{change_intelligence,incident_memory,verification_readiness,release_context}.py
  fabric/{inputs,security_preflight,controller,verdict,publisher}.py
  adapters/{github,foundry}.py
```

Do not create these all at once. Follow the migration order in [01](01-Architecture-and-Migration.md).
