# SafeLane v2 — Requirements

This file lists every dependency SafeLane v2 needs, based on the existing `requirements.txt` files (root, `platform/`, `function_deploy/`) plus what the Security Preflight addition needs. Everything is in one fenced block per component so you can copy-paste directly into the matching `requirements.txt`.

**How to read "Required" vs "Optional":** *Required* means the core pipeline will not start, or will silently do less than it should, without it. *Optional* means SafeLane already has a working fallback and the dependency only unlocks a richer feature (LLM enrichment, tracing, incident history, etc.).

---

## 1. Core Python Dependencies (Required)

These run the Fabric Controller's basic HTTP surface and data contracts, with no external service needed.

```
fastapi
uvicorn
pydantic>=2.0
python-dotenv
aiohttp
httpx
```

## 2. FastAPI / Web Layer (Required)

Already covered by the block above (`fastapi`, `uvicorn`); listed separately here only to make the mapping to the PRD's "FastAPI dependencies" explicit. No additional packages needed.

## 3. GitHub Integration Dependencies (Required)

SafeLane talks to GitHub over plain REST via `httpx` (already listed above) — no separate GitHub SDK is required. If you choose to use the Model Context Protocol client path for local diff-fetching (`agents/diff_analyst/mcp_client.py`), also install:

```
mcp
```

*Optional* — only needed if you run `diff_agent.py::run_from_pr()` locally via MCP; not required for the production webhook/orchestrator path, which receives the diff directly from the Controller.

## 4. Pydantic Dependencies (Required)

```
pydantic>=2.0
```

Already included above — SafeLane's entire data-contract layer (`AgentResult`, `RepoContext`, `PRPayload`, `VerdictReport`) is built on Pydantic v2. Do not downgrade to v1 syntax.

## 5. Azure Dependencies (Optional — richer features, not required to run)

```
# Azure OpenAI / LLM enrichment (Change Intelligence text, Verdict brief wording)
openai
semantic-kernel>=1.0
azure-identity>=1.25.2
azure-ai-projects
azure-ai-contentsafety
```

Without these installed/configured, Change Intelligence runs on heuristics only, and the Verdict & Policy Layer publishes the deterministic template brief — both fully functional, just less richly worded.

## 6. Microsoft Foundry-Related Dependencies (Optional — student-subscription dependent)

```
azure-ai-projects
azure-identity>=1.25.2
```

(Same packages as §5 — Foundry project connectivity reuses the Azure Identity + AI Projects SDKs.) Every function in `foundry/deployment_config/__init__.py` checks for these and for the relevant environment variables before use, and returns `None`/a no-op otherwise. **Never make a required code path import these directly without a try/except fallback.**

## 7. Azure AI Search Dependencies (Optional — Incident Memory data backend)

```
azure-search-documents==11.4.0
azure-monitor-query==1.2.0
```

Without these, Incident Memory reports "no deployment connection — no relevant incident history available" and contributes a safe, neutral `pass` result rather than failing.

## 8. Database Dependencies (Required for the Setup Platform)

```
sqlalchemy[asyncio]>=2.0.0
aiosqlite>=0.19.0
asyncpg>=0.29.0
PyJWT>=2.8.0
cryptography>=41.0.0
```

- `aiosqlite` powers the default local dev database (`sqlite+aiosqlite:///...`) — required for local development.
- `asyncpg` is only exercised if `DATABASE_URL` points at PostgreSQL — required for a production deployment, not for local dev.
- `PyJWT` and `cryptography` are required unconditionally — they back session auth and PAT encryption respectively.

## 9. Observability Dependencies (Optional — degrades to standard `logging` without them)

```
azure-monitor-opentelemetry>=1.8.6
azure-monitor-opentelemetry-exporter>=1.0.0b36
opentelemetry-sdk>=1.39.0
opentelemetry-api>=1.39.0
opentelemetry-instrumentation-openai-v2
```

**Version note carried over from the existing project:** `azure-monitor-opentelemetry-exporter>=1.0.0b36` requires `opentelemetry-sdk` **1.39.x**, not 1.40.x, due to a breaking `LogData` import change upstream. Pin accordingly if you see import errors after an update.

## 10. Testing Dependencies (Required for development)

```
pytest
pytest-asyncio
```

`pytest-asyncio` is required because the entire test suite runs with `asyncio_mode = "auto"` (configured in `pyproject.toml`) — every `async def test_...` function is collected and run without extra decorators.

## 11. Platform-Specific Dependencies (Required for `platform/`)

```
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
msal>=1.25.0
python-dotenv>=1.0.0
pydantic>=2.0.0
PyJWT>=2.8.0
cryptography>=41.0.0
sqlalchemy[asyncio]>=2.0.0
aiosqlite>=0.19.0
asyncpg>=0.29.0
```

`msal` is required specifically for the Azure AD OAuth flow used when a user connects their Log Analytics workspace during setup (`platform/server/services/azure_service.py`). If you're skipping Azure workspace linking entirely for a minimal demo, you can omit `msal`, but the "connect Azure" step in the Setup Platform UI will not function.

## 12. Function-App-Specific Dependencies (Optional — only for the incident-ingestion pipeline)

```
azure-functions
azure-identity>=1.25.2
azure-core
azure-search-documents==11.4.0
azure-monitor-query==1.2.0
openai
python-dotenv
asyncpg>=0.29.0
```

Only needed if you deploy `function_deploy/` to keep Incident Memory's index automatically fresh from live production alerts/logs. For a hackathon demo, you can instead seed sample incidents once via `mcp_servers/azure_mcp_server/sample_data.py::upload_sample_data()` and skip standing up the Azure Function entirely.

## 13. Optional Dependencies Summary

```
# Everything in this block is optional. SafeLane runs correctly without any
# of it — you get a working, explainable, deterministic pipeline either way.
# Install these only when you want the richer/enhanced behavior described.

openai                              # LLM enrichment of findings/brief text
semantic-kernel>=1.0                # "Microsoft Agent Framework" branding / plugin wrapping
azure-ai-projects                   # Microsoft Foundry project connectivity
azure-ai-contentsafety              # Content-safety screen on LLM-generated brief text
azure-search-documents==11.4.0      # Incident Memory's real incident history
azure-monitor-query==1.2.0          # Log Analytics querying for incident ingestion
azure-monitor-opentelemetry>=1.8.6  # Tracing/observability export to App Insights / Foundry
mcp                                 # Local MCP-based diff fetching (dev convenience only)
azure-functions                     # Only needed to deploy the ingestion pipeline as an Azure Function
```

## 14. Full `requirements.txt` (root, copy-pasteable)

```
# ── Core (Required) ──
fastapi
uvicorn
pydantic>=2.0
python-dotenv
aiohttp
httpx

# ── Azure OpenAI & AI Services (Optional) ──
openai
semantic-kernel>=1.0
azure-identity>=1.25.2
azure-ai-projects
azure-ai-contentsafety

# ── Azure AI Search — Incident Memory (Optional) ──
azure-search-documents==11.4.0
azure-monitor-query==1.2.0

# ── Observability — Foundry / App Insights (Optional) ──
# Pin opentelemetry-sdk to 1.39.x, NOT 1.40.x — see §9 note above.
azure-monitor-opentelemetry>=1.8.6
azure-monitor-opentelemetry-exporter>=1.0.0b36
opentelemetry-sdk>=1.39.0
opentelemetry-api>=1.39.0
opentelemetry-instrumentation-openai-v2

# ── MCP Client — local dev diff fetching (Optional) ──
mcp

# ── Platform DB — registration lookup in orchestrator (Required) ──
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
PyJWT>=2.8.0
cryptography>=41.0.0

# ── Testing (Required for development) ──
pytest
pytest-asyncio
```

## 15. Which Dependencies Are Required vs Optional — Quick Reference

| Category | Required for a minimal working demo? | Notes |
|---|---|---|
| Core (fastapi, uvicorn, pydantic, httpx, python-dotenv, aiohttp) | ✅ Yes | Nothing runs without these |
| Setup Platform DB (sqlalchemy, aiosqlite/asyncpg, PyJWT, cryptography) | ✅ Yes | Needed for registration + auth, even locally with SQLite |
| pytest / pytest-asyncio | ✅ Yes, for development | Not needed to *run* SafeLane, needed to *develop* it safely |
| openai / semantic-kernel / azure-ai-projects / azure-ai-contentsafety | ❌ No | Unlocks LLM enrichment; heuristics/templates work without it |
| azure-search-documents / azure-monitor-query | ❌ No | Unlocks real Incident Memory history; reports "no history" cleanly without it |
| azure-monitor-opentelemetry* / opentelemetry-* | ❌ No | Unlocks tracing dashboards; standard logging works without it |
| mcp | ❌ No | Local dev convenience only |
| azure-functions | ❌ No | Only for deploying the background ingestion pipeline |
| msal (platform only) | ⚠️ Only if using Azure workspace linking in Setup | Skip if you're not connecting Incident Memory to a real Azure workspace |
