# 10 — Platform, Foundry, and Ingestion

## Setup Platform

| Item | Value |
|---|---|
| Existing source | `platform/server/`, `platform/frontend/` |
| New architecture name | Setup Platform |
| Action | Reuse; refactor workflow template carefully |
| Risk | Medium-high: OAuth, encrypted PATs, and repository writes. |
| Tests | Platform route tests, database tests, disposable-repository workflow test |

Keep it independent from Fabric code. It may store a registration and install a workflow, but it should know analysis only through an orchestrator URL.

`platform/server/services/github_service.py` needs a careful v2 workflow-template update. Use least-privilege GitHub Actions permissions and do not require a human PAT solely to trigger a model response.

## Registration database

**Existing source:** `platform/server/services/db.py`  
**Action:** Reuse, then extend.

Keep `RegistrationRow` and encrypted PAT storage. Add an `analysis_runs` table only when durable run status/idempotency is implemented. Before a production deployment, correct the current PostgreSQL TLS branch: certificate validation must not be disabled.

## Optional Foundry Adapter

| Existing source | New architecture name | Action |
|---|---|---|
| `foundry/deployment_config/` | Optional Foundry Adapter | Wrap |

Foundry can provide tracing, optional narration, and optional content-safety enrichment. The deterministic Fabric, Security Preflight, and verdict must work without it. Do not duplicate or replace local Security Preflight with a paid/cloud model call.

## Incident ingestion

| Existing source | New architecture name | Action |
|---|---|---|
| `mcp_servers/azure_mcp_server/` | Incident Memory store/ingestion adapter | Reuse and wrap |
| `function_deploy/function_app.py` | Incident Memory ingestion deployment | Reuse |

The Azure Function timer, Event Grid trigger, and HTTP backfill ingest incidents into the Incident Memory store. They are not part of the synchronous PR analysis path and must remain independently deployable.

## Checklist

- [ ] The application works with Foundry environment variables absent.
- [ ] The demo works with mock incident data and no Azure credentials.
- [ ] PATs are encrypted at rest and never logged or returned by browser routes.
- [ ] Workflow installation is tested only in a disposable repository during development.
