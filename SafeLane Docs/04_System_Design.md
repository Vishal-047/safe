# SafeLane v2 — System Design Document

**Companion files:** `03_Architecture.md`, `08_Code_Integration_Map.md`, `05_Requirements.md`

This document is the detailed engineering reference. It specifies contracts, flows, and operational behavior precisely enough that a coding agent can implement against it without re-deriving decisions already made in the existing codebase.

---

## 1. Component Responsibilities & Service Boundaries

| Component | Responsibility | Does NOT do |
|---|---|---|
| **Fabric Controller** (`agents/orchestrator/`) | Parse PR events, resolve `RepoContext`, dispatch Evidence Modules concurrently, invoke the Verdict layer, invoke the Publisher | Does not itself compute risk scores; does not itself talk to GitHub's write endpoints outside the Publisher path |
| **Change Intelligence** (`agents/diff_analyst/`) | Score a diff for dangerous patterns | Does not fetch the diff itself in production (receives it from the Controller); does not decide the final verdict |
| **Incident Memory** (`agents/history_agent/` + `mcp_servers/azure_mcp_server/`) | Correlate changed files with past incidents | Does not ingest incidents itself (that's `function_deploy/`); does not own the Azure Search index lifecycle beyond querying it |
| **Verification Readiness** (`agents/coverage_agent/`) | Detect missing/deleted tests; nudge Copilot | Does not write tests itself; does not merge or approve PRs |
| **Release Context** (`agents/timing_agent/`) | Score deploy-window risk | Makes no network calls; has no side effects |
| **Verdict & Policy Layer** (`agents/verdict_agent/`) | Compute score, decision, risk brief, rollback playbook | Never calls GitHub directly; never mutates state |
| **Fixed-template GitHub publisher** (`server.py` PR-comment functions + `github_service.py` workflow template) | The only code path allowed to write to GitHub on SafeLane's behalf | Never accepts free-form model output as the thing it posts — only structured, validated data filled into fixed templates |
| **Setup Platform** (`platform/`) | Onboarding, registration storage, credential encryption | Has zero import dependency on `agents/`, `mcp_servers/`, or `foundry/` — communicates with the Fabric Controller only via its public URL |
| **Incident ingestion** (`function_deploy/`, `mcp_servers/azure_mcp_server/ingest.py`) | Keep the Incident Memory index fresh from Azure Monitor/Log Analytics | Does not run on the PR-analysis critical path — fully async/background |
| **Foundry governance** (`foundry/deployment_config/`) | Optional tracing, content safety, policy guardrails, quality eval | Never required for correctness — every function degrades to a safe no-op |

## 2. Shared Data Contracts

Single source of truth: `agents/shared/data_contract.py`. Do not duplicate these shapes elsewhere.

### 2.1 `AgentResult` (every Evidence Module returns exactly this)

```python
class AgentResult(BaseModel):
    agent_name: str                 # e.g. "Diff Analyst" (kept as internal id; display name mapped in docs/UI)
    risk_score_modifier: int        # 0–100, enforced by Pydantic (ge=0, le=100)
    status: Literal["pass", "warning", "critical"]
    findings: list[str] = []
    recommended_action: str
```

### 2.2 `RepoContext` (per-registration credentials/config, flows through the pipeline)

```python
class RepoContext(BaseModel):
    registration_id: str | None
    owner: str
    repo: str
    gh_token: str | None                 # decrypted PAT, in-memory only
    azure_search_endpoint: str | None
    azure_search_key: str | None
    azure_tenant_id: str | None
    azure_workspace_id: str | None
    azure_customer_id: str | None
    azure_search_index: str | None       # derive_index_name(owner, repo)
```

### 2.3 `PRPayload` (`agents/orchestrator/__init__.py`)

```python
class PRPayload(BaseModel):
    pr_number: int
    repo: str                    # "owner/repo"
    changed_files: list[str] = []
    diff: str = ""
    timestamp: datetime | None = None
    head_sha: str | None = None
    skip_autofix: bool = False
```

### 2.4 `VerdictReport` (Verdict & Policy Layer output)

```python
class VerdictReport(BaseModel):
    confidence_score: int              # 0–100
    decision: Literal["greenlight", "blocked"]
    risk_brief: str                    # markdown
    rollback_playbook: str | None      # markdown, only when blocked
    agent_results: list[AgentResult]
```

**Enforced invariants** (Pydantic `model_validator`, not just convention):
- Any `AgentResult.status == "critical"` ⇒ `decision` **must** be `"blocked"`.
- `confidence_score < 70` ⇒ `decision` **must** be `"blocked"`.
- `decision == "greenlight"` ⇒ `rollback_playbook` **must** be `None`.

These invariants mean a caller can trust `VerdictReport` without re-deriving the decision logic — construction itself fails if they're violated.

## 3. Evidence-Module Contracts (function signatures the Controller calls)

```python
# Change Intelligence
async def run(diff: str, changed_files: list[str]) -> AgentResult

# Incident Memory
async def run(changed_files: list[str], repo_ctx: RepoContext | None = None) -> AgentResult

# Verification Readiness
async def run(pr_number: int, repo: str, skip_autofix: bool = False, gh_token: str | None = None) -> AgentResult

# Release Context
async def run(deploy_timestamp: datetime | None = None, release_date: date | None = None) -> AgentResult
```

All four are `async def`, all return `AgentResult`, and the Controller wraps each in `asyncio.wait_for(..., timeout=30)` inside a single `asyncio.gather(..., return_exceptions=True)` — see §8.

## 4. Verdict & Scoring Logic

```python
AGENT_WEIGHTS = {
    "Diff Analyst":    0.30,   # Change Intelligence
    "History Agent":   0.25,   # Incident Memory
    "Coverage Agent":  0.25,   # Verification Readiness
    "Timing Agent":    0.20,   # Release Context
}

def compute_score(results: list[AgentResult]) -> int:
    weighted_sum = sum(r.risk_score_modifier * AGENT_WEIGHTS.get(r.agent_name, 0.25) for r in results)
    return int(max(0, min(100, 100 - weighted_sum)))

def decide(score: int, results: list[AgentResult]) -> str:
    has_critical = any(r.status == "critical" for r in results)
    return "blocked" if (has_critical or score < 70) else "greenlight"
```

The risk brief and (if blocked) rollback playbook are built from a fixed markdown template first (`_build_risk_brief`, `_build_rollback_playbook`), then **optionally** rewritten by an LLM call for readability. The LLM call receives the already-computed template as context and is instructed to preserve structure — it cannot alter the score or decision, and its output is discarded (falls back to the template) on any failure or a Content Safety flag.

## 5. GitHub Webhook Flow

```text
POST /webhook/pr
  Headers: X-Hub-Signature-256, X-GitHub-Event
  1. Read raw body bytes.
  2. Verify HMAC-SHA256 signature against GITHUB_WEBHOOK_SECRET.
     -> 401 if invalid.
  3. If X-GitHub-Event != "pull_request" -> 200 {"status": "ignored"}.
  4. Parse action (opened|synchronize|reopened only) -> PRPayload skeleton.
     -> 200 {"status": "ignored"} for other actions.
  5. Validate repo + pr_number present -> 400 if malformed.
  6. Look up RepoContext for payload.repo -> 404 if no active registration.
  7. Schedule background task _run_orchestration(payload, repo_ctx).
  8. Return 202 {"status": "accepted", "pr_number": ...} immediately.

Background task:
  a. Fetch changed_files + diff via GitHub API (paginated file list; diff via
     the .v3.diff Accept header).
  b. orchestrate(payload, repo_ctx) -> VerdictReport.
  c. apply_policy_guardrails(verdict, payload) [optional, Foundry].
  d. Build fixed-template PR comment, POST it to GitHub.
```

## 6. Pull-Request Analysis Flow (`POST /analyze`)

Used by the self-installed Actions workflow and for manual/demo triggering. Same core pipeline as the webhook path, but synchronous (caller waits for the `VerdictReport` JSON) and gated by the freemium `check_freemium_limit` dependency (`X-Client-ID` header required; 402 once the free-tier cap is hit). Returns the full `VerdictReport.model_dump()` plus an optional `guardrails` block.

## 7. Security Preflight Flow — **new in v2, spec for the coding agent to build**

This is the one genuinely new module referenced throughout this doc set. It does not exist as a distinct file yet; the existing `SafeLane Docs/System Design, Architecture & Open-Source Tech Stack.md` (already in the repo) sketches it, and the following operationalizes it against the real code.

**Purpose:** enforce the untrusted-input boundary *before* any PR text reaches an LLM prompt, and catch a handful of zero-cost, high-signal cyber-risk patterns that the four Evidence Modules don't specifically target (CI/CD hardening, transport/auth weakening, IaC/dependency exposure, prompt-injection-shaped text).

**Where it runs:** as a synchronous, deterministic step inside the Fabric Controller, immediately after fetching the diff/changed files and *before* the four Evidence Modules are dispatched (it can run in parallel with them, but its findings must be available to the Verdict layer before publishing).

**Contract (mirrors `AgentResult` so it composes with the existing aggregation code):**

```python
class SecurityFinding(BaseModel):
    rule_id: str
    severity: Literal["info", "warning", "critical"]
    file: str | None
    evidence: str        # short, specific, never echoes a raw secret value
    remediation: str
```

**Rule families to implement (pure Python stdlib + regex, no new paid dependency):**

| Family | Example signals | Default outcome |
|---|---|---|
| Secret exposure | Reuses/extends `agents/diff_analyst/diff_agent.py::SECRET_PATTERNS` | critical |
| CI/CD hardening | `pull_request_target`, `permissions: write-all`, unpinned third-party actions, `curl \| sh` | warning/critical |
| Code execution | `eval(`, `exec(`, `subprocess(..., shell=True)`, unsafe deserialization | warning |
| Transport/auth | `verify=False`, disabled TLS checks, removed auth middleware | warning/critical |
| Dependency/IaC | lockfile changes, public ingress, wildcard IAM roles | flag for review |
| Prompt-injection shaped text | instruction-like phrases in PR title/body/comments ("ignore previous instructions", role-impersonation framing) | warning; content is still only ever treated as data |

**Scoring integration:**

```python
SECURITY_PENALTIES = {"info": 0, "warning": 8, "critical": 25}

def apply_security_policy(module_score: int, findings: list[SecurityFinding]) -> tuple[int, bool]:
    penalty = min(sum(SECURITY_PENALTIES[f.severity] for f in findings), 40)  # capped
    has_blocker = any(f.severity == "critical" for f in findings)
    final_score = max(0, module_score - penalty)
    return final_score, has_blocker
```

Apply this **after** `compute_score()` and **before** `decide()`: a `has_blocker=True` result forces `blocked` exactly like an Evidence Module `critical` status does today, reusing the same invariant already enforced on `VerdictReport`.

**Failure handling:** a Preflight crash or an empty rule set must return a `warning`-level result and must **not** allow an automatic `greenlight` — same fail-conservative principle already used for Evidence Module timeouts.

**Testing:** build a fixture suite under `tests/unit/test_security_preflight.py` mirroring the existing fixture style in `tests/unit/test_diff_analyst.py`, covering: safe diff, fake credential, private-key block, unpinned-action workflow, `verify=False` diff, and a prompt-injection-shaped PR body. Assert severity, `has_blocker`, and that no rule ever echoes a real-looking secret value into its `evidence` field.

## 8. Fixed-template Publishing Flow

```text
VerdictReport
   |
   v
_build_pr_comment(verdict) -> markdown string
   - Fixed header, fixed emoji map, fixed table structure
   - risk_brief and rollback_playbook are inserted verbatim inside
     <details> blocks, never re-interpreted or executed
   |
   v
_post_pr_comment(repo, pr_number, body, token)
   - POST /repos/{repo}/issues/{pr_number}/comments
   - Logs a warning on failure; does not currently retry (see §9)
```

The Actions-workflow-embedded publisher (`WORKFLOW_TEMPLATE` in `github_service.py`) follows the identical structure in JavaScript, posted via `github.rest.pulls.createReview(..., event: 'COMMENT')` so it is attributable to the workflow's own GitHub identity (using `GH_PAT`, not the default `github-actions[bot]`, specifically so GitHub Copilot Coding Agent will respond to the `@copilot` mention — this is a deliberate, documented design choice, not an oversight).

## 9. Error Handling, Timeouts, Retries

| Failure point | Current behavior | v2 recommendation |
|---|---|---|
| Evidence Module raises or exceeds 30s | Replaced with a conservative `warning` `AgentResult` (`_make_fallback`) | Keep as-is; already correct |
| Verdict Agent import/runtime error | Pipeline returns a hard `blocked` `VerdictReport` | Keep as-is; already correct (fail-closed) |
| LLM call fails (Change Intelligence or Verdict brief) | Falls back to heuristic/template | Keep as-is; already correct |
| GitHub comment POST fails | Logged as a warning, no retry | **Add bounded retry** (e.g. 3 attempts, exponential backoff via `httpx` + `tenacity` or a small hand-rolled loop) since a silently-missing PR comment is a worse failure mode than a few seconds of extra latency |
| GitHub file-list/diff fetch fails | Logged as a warning, proceeds with empty list/diff | Acceptable for hackathon; document that this degrades Change Intelligence/Verification Readiness quality rather than crashing |
| Webhook signature invalid | 401, request dropped | Keep as-is; already correct |
| No active registration | 404, request dropped, no orchestration | Keep as-is; already correct |

## 10. Logging & Observability

- Standard `logging` module throughout, namespaced `prism.*` (`prism.orchestrator`, `prism.server`, `prism.history_agent`, `prism.verdict`, `prism.foundry`, etc.) — keep this namespace convention for any new module (e.g. `prism.security_preflight`).
- Noisy third-party loggers (`azure`, `urllib3`, `opentelemetry`, `httpcore`) are explicitly silenced to `WARNING` in `server.py` — replicate this in the Setup Platform's `app.py` if it becomes noisy too.
- When Foundry is connected: OpenTelemetry spans per agent call (`trace_agent_call`) and per full run (`trace_orchestrate`), exported to Application Insights, with `prism.agent.*` and `prism.confidence_score`/`prism.decision` attributes attached.
- Audit entries for every verdict via `apply_policy_guardrails` → `_log_audit_entry` (logged always; exported as a span when Foundry is available).

## 11. Storage

| Store | Engine | Purpose |
|---|---|---|
| Setup Platform DB | SQLite (dev, `sqlite+aiosqlite`) / PostgreSQL (prod, `asyncpg`) | `users`, `registrations` tables (see schema in `platform/server/services/db.py`) |
| Incident Memory index | Azure AI Search, one index per repo (`derive_index_name`) | Past-incident documents, queried by file path / semantic text |
| Freemium usage | In-memory dict (`USAGE_TRACKER`) | Per-`X-Client-ID` call counts, 30-day rolling eviction — **not shared across replicas**, flagged in §12 |

## 12. Authentication, Authorization, Secrets Management

- **User auth (Setup Platform):** GitHub OAuth → JWT session cookie (`platform/server/services/auth_service.py`), `HS256`, 24h expiry.
- **Repo auth (analysis calls):** the registration's own encrypted GitHub PAT, decrypted in-memory only at request time, never logged.
- **PAT encryption:** Fernet (AES) via `ENCRYPTION_KEY`; `encrypt_pat`/`decrypt_pat` raise clearly if the key is missing (fail-closed — good).
- **Webhook auth:** HMAC-SHA256 against `GITHUB_WEBHOOK_SECRET`.
- **Azure Log Analytics cross-tenant access:** `azure_tenant_id` stored per registration to support a customer's own AAD tenant.

### 12.1 Code-review findings — apply the `/code-review` lens (security, performance, correctness, maintainability)

These were found while reading the existing code for this document set. None block a hackathon demo; all should be fixed before any real/public deployment. Each includes the file and the concrete fix.

| # | File | Issue | Severity | Fix |
|---|---|---|---|---|
| 1 | `platform/server/services/auth_service.py` | `JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")` — insecure hardcoded fallback; if the env var is ever unset in a deployed environment, sessions are signed with a publicly-known secret | 🔴 Critical (security) | Remove the default. Raise at startup if `JWT_SECRET` is unset, mirroring the fail-closed pattern already used for `ENCRYPTION_KEY` in the same file. |
| 2 | `platform/server/services/db.py` | `_ssl_ctx.check_hostname = False; _ssl_ctx.verify_mode = ssl.CERT_NONE` for the PostgreSQL connection — disables TLS certificate verification, opening a MITM risk on the DB connection | 🔴 Critical (security) | Use Azure PostgreSQL's actual CA bundle (`ssl.create_default_context()` without disabling verification), or at minimum gate the insecure context behind an explicit `DB_SSL_INSECURE=true` dev-only flag with a loud warning log. |
| 3 | `agents/diff_analyst/diff_agent.py` via `llm_client.py::call_llm` | `call_llm()` is a **synchronous** (blocking) OpenAI SDK call, invoked directly inside the `async def run()` path used by Change Intelligence. Because it isn't wrapped in `asyncio.to_thread` (unlike Incident Memory's Azure Search call, which correctly does this), it blocks the event loop for the duration of the network call — reducing the real concurrency benefit of `asyncio.gather` across all four modules | 🟡 Performance/Correctness | Wrap the call: `await asyncio.to_thread(call_llm, SYSTEM_PROMPT, context_prefix + diff_text)`, or switch to the async OpenAI client (`AsyncAzureOpenAI`, already used elsewhere in `verdict_agent`) for consistency. |
| 4 | `agents/orchestrator/server.py`, `platform/server/routers/github_setup.py` | Hardcoded fallback orchestrator URLs baked into source (an `azurecontainerapps.io` URL and an `ngrok-free.dev` URL) | 🟡 Maintainability | Require `PRISM_ORCHESTRATOR_URL` via environment/config with no code-level default; fail loudly at startup if unset in production, keep a clearly-labeled `localhost` default only for local dev. |
| 5 | `agents/orchestrator/server.py::_verify_signature` | Webhook signature check silently "succeeds" (skips verification) when `GITHUB_WEBHOOK_SECRET` is unset — safe default for local dev, dangerous if forgotten in a real deployment | 🟡 Security | Keep the dev-mode bypass, but log a prominent `WARNING` on every request when it's active, and consider refusing to bind on `0.0.0.0` (only `127.0.0.1`) while the secret is unset. |
| 6 | `agents/orchestrator/server.py` | `USAGE_TRACKER` is an in-memory dict — resets on restart and isn't shared across horizontally-scaled replicas | 🟢 Scalability (not a hackathon blocker) | Acceptable for the demo; move to Redis/Postgres before any multi-instance production deployment (already noted in `03_Architecture.md` §15). |
| 7 | `agents/coverage_agent/__init__.py` | Coverage checks make one GitHub API call per changed Python file to check test-file existence (`GET /repos/{repo}/contents/{expected_test}`) — O(n) API calls per PR | 🟢 Performance | Fine at hackathon PR sizes; if PRs regularly touch dozens of files, batch via a single tree listing (`GET /repos/{repo}/git/trees/{sha}?recursive=1`) and check membership locally instead. |

### 12.2 What already looks good (worth preserving exactly as-is)

- Every external call in the pipeline has a bounded timeout and a conservative, explained fallback — this is the single most important property to preserve through any refactor.
- `VerdictReport`'s Pydantic invariants make "the AI silently downgraded a critical finding" structurally impossible, not just conventionally discouraged.
- PAT encryption, JWT signing, and HMAC webhook verification are all present and use standard, well-regarded libraries (`cryptography`, `PyJWT`) correctly (aside from finding #1 above).
- The Setup Platform's hard architectural boundary (zero imports from `agents/`/`mcp_servers/`/`foundry/`) is a genuinely good design decision — it keeps onboarding changes from ever being able to break analysis, and vice versa. Do not blur this boundary while adding the Security Preflight module.

## 13. Testing Strategy

The existing suite already follows a clean two-tier structure — extend it, don't replace it.

```text
pytest.ini markers (pyproject.toml):
  unit             — pure mock/unit test, no real I/O          (tests/unit/)
  integration      — real agent logic, external Azure stubbed  (tests/integration/)
  azure_required   — needs live Azure creds, auto-skipped if absent
  foundry_required — needs live Foundry creds, auto-skipped if absent
```

| Layer | Existing coverage | v2 additions needed |
|---|---|---|
| Unit | `test_diff_analyst.py`, `test_history_agent.py`, `test_timing_agent.py`, `test_verdict_agent.py`, `test_orchestrator.py`, `test_server.py`, `test_foundry.py` | `test_security_preflight.py` (see §7) |
| Integration | `test_e2e_agents.py`, `test_e2e_pipeline.py`, `test_e2e_server.py`, `test_e2e_live_foundry.py` | Extend `test_e2e_pipeline.py` to include a Security-Preflight-triggering fixture PR |
| Live/manual scripts | `test_live_orchestrator.py`, `test_live_parts.py`, `test_simulate_alert.py`, `_quick_search.py` | No changes needed |

Run commands (already configured, `asyncio_mode = "auto"`):

```bash
pytest                       # everything (foundry_required auto-skips without creds)
pytest -m unit                # fast, no external dependency
pytest -m integration          # end-to-end, Azure calls stubbed
pytest -m "unit or integration"
pytest -m foundry_required -v  # only with live creds — appears in the Foundry dashboard
```

## 14. Local Development Flow

```bash
# Terminal 1 — Fabric Controller
uvicorn agents.orchestrator.server:app --reload --port 8000

# Terminal 2 — Setup Platform
cd platform && uvicorn server.app:app --reload --port 8080

# Terminal 3 — expose the Controller for a real GitHub webhook (optional for local-only testing)
ngrok http 8000
```

See `07_Beginner_Vibe_Coding_Guide.md` for the fully hand-held version of this flow, including how to get a GitHub PAT and where to paste it.

## 15. Deployment Flow (production-shaped, optional for the hackathon)

```text
foundry/deployment_config/infra/infra.bicep       — shared infra (Postgres, Search, App Insights, Container Apps env)
foundry/deployment_config/orchestrator/*.bicep     — Fabric Controller container app + Dockerfile
foundry/deployment_config/platform/*.bicep         — Setup Platform container app + Dockerfile
foundry/deployment_config/*.ps1                    — deploy.ps1 / cleanup.ps1 / generate-env.ps1 scripts
.github/workflows/deploy-azure.yml                 — CI-driven deploy of the orchestrator
.github/workflows/deploy-platform.yml              — CI-driven deploy of the platform
```

Not required to demo SafeLane — the local dev flow above is sufficient for hackathon judging. Use this section only if you decide to stand up a persistent hosted demo instance.

## 16. Backtesting and Validation

- Build (or extend) a small **fixture PR corpus**: one clean PR, one with each individual risk type (secret, removed retry, schema change, deleted test, Friday-4:58PM timestamp), and one combined worst-case PR.
- For each fixture, assert: the expected module status, the expected score band, and the expected `decision`.
- Extend this corpus with the Security Preflight fixtures from §7 once that module exists.
- Track false positives/negatives separately per module so tuning `AGENT_WEIGHTS` or a module's internal thresholds is measurable rather than anecdotal — this mirrors the validation approach already sketched in the repo's existing `SafeLane Docs/System Design, Architecture & Open-Source Tech Stack.md` §7, which this document operationalizes against the real code paths.
