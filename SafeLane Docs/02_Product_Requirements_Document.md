# SafeLane v2 — Product Requirements Document (PRD)

**Status:** Draft for hackathon build
**Audience:** You (product owner), and any coding agent building this
**Companion files:** `03_Architecture.md`, `04_System_Design.md`, `08_Code_Integration_Map.md`

---

## 1. Product Vision

Every engineer has shipped a change where tests passed, the linter was clean, and production still broke. SafeLane exists because **"tests pass" is not the same thing as "safe to ship."**

SafeLane v2 is the **Change Assurance Fabric** for GitHub pull requests: an agentic system that reads a PR the way a careful senior engineer would — checking the diff for dangerous patterns, checking whether the touched files have caused trouble before, checking whether tests actually cover the new code, and checking whether *now* is a smart time to deploy. It turns those four perspectives into one number — the **Deployment Confidence Score (0–100)** — and a plain-English explanation, posted directly on the pull request.

## 2. Problem Statement

CI/CD pipelines today are binary and stateless. They answer one question — "did the tests pass?" — and nothing else. They never ask:

- Has this file caused production incidents before?
- Did test coverage actually drop for the new code paths?
- Are we deploying at 4:58 PM on a Friday before a long weekend?
- Was retry logic quietly removed from a payment-critical path?

The result: preventable incidents, 2 AM postmortems, and engineers who are afraid to merge. SafeLane replaces the binary pass/fail gate with a graded, explainable, evidence-based judgment.

## 3. Target Users

| User | What they need from SafeLane |
|---|---|
| **Individual contributor / student engineer** (you, and people like you) | A safety net that catches mistakes before a reviewer does, with plain-English explanations they can learn from. |
| **Small team lead / repo maintainer** | Confidence that a merge won't blow up production, without reading every diff line-by-line. |
| **Hackathon judge / evaluator** | A fast, legible demo that proves the idea works on a real PR, in under two minutes. |
| **Future SaaS customer (post-hackathon)** | A GitHub-native tool that installs in minutes, costs nothing to trial, and doesn't require them to trust a black box. |

## 4. User Needs

- "I want to know *why* a PR is risky, not just that it is."
- "I don't want to configure a security platform to get basic protection."
- "I don't want the AI to be able to do anything dangerous on its own — I want it to explain, and a fixed process to act."
- "I want this to work even if the AI service is down."
- "I want to see this work on a real repository, live, during a demo."

## 5. Product Goals

- G1: Give every PR a single, explainable **Deployment Confidence Score (0–100)**.
- G2: Cover four independent risk perspectives — Change Intelligence, Incident Memory, Verification Readiness, Release Context — each contributing an auditable, weighted portion of the score.
- G3: Post the verdict directly to the PR as a GitHub comment, using a **fixed, non-model-controlled template**.
- G4: Automatically nudge test-coverage gaps toward a fix (via a GitHub Copilot-triggering comment) rather than only flagging them.
- G5: Run reliably with zero paid services, and get measurably better when optional paid/Azure/Foundry services are connected.
- G6: Be installable into any GitHub repository by a non-expert in under 10 minutes via the Setup Platform.

## 6. Non-Goals

- SafeLane is **not** a general-purpose static analysis / SAST platform. It scores deployment risk, not full code quality.
- SafeLane does **not** replace human code review — it augments it.
- SafeLane does **not** grant the AI models any ability to merge, deploy, change permissions, or run commands. All GitHub-facing actions are template-driven.
- SafeLane v2 does **not** require the VS Code extension to demo or operate. It is retained in the repository but is out of scope for the hackathon build (see `08_Code_Integration_Map.md`).
- SafeLane is not (yet) a fully generalized enterprise security-scanning product; the deterministic Security Preflight described in this doc set is a lightweight, zero-cost addition, not a Semgrep/Snyk replacement.

## 7. Core User Journeys

**Journey A — First-time setup (repo maintainer)**
1. Opens the SafeLane Setup Platform in a browser.
2. Logs in / enters a GitHub Personal Access Token.
3. Selects a target repository.
4. SafeLane commits a fixed-template GitHub Actions workflow (`prism-gate.yml` / `SafeLane-gate.yml`) into `.github/workflows/`.
5. (Optional) Connects an Azure Log Analytics workspace so Incident Memory has real incident history to learn from.
6. Sees a "Ready" status once the workflow and (optional) secrets are confirmed.

**Journey B — A PR is opened (day-to-day use)**
1. A contributor opens or updates a PR.
2. The fixed-template GitHub Actions workflow fires automatically.
3. It calls the SafeLane orchestrator (Change Assurance Fabric Controller), which runs all four Evidence Modules concurrently.
4. Within seconds to ~1 minute, SafeLane posts a PR comment: score, per-module status table, full risk brief, and (if blocked) a rollback playbook.
5. If the score is below the threshold, the PR is marked failing/blocked; a maintainer with write access can still override and merge.
6. If missing tests were the main issue, SafeLane also posts an `@copilot`-addressed comment asking GitHub Copilot Coding Agent to generate the missing tests.

**Journey C — Hackathon demo (judge-facing)**
1. Presenter opens a prepared PR with an intentionally risky change (e.g., a removed retry block).
2. SafeLane's comment appears live, or a pre-captured run is shown if live network access is unreliable.
3. Presenter narrates the four modules and the score in under two minutes.

## 8. Main Features

| Feature | Description | Status in existing code |
|---|---|---|
| Deployment Confidence Score | Weighted 0–100 score combining four modules | ✅ Implemented (`agents/verdict_agent`) |
| Change Intelligence | Diff scanning for secrets, removed error-handling, removed retries/timeouts, risky schema changes | ✅ Implemented (`agents/diff_analyst`), heuristic + optional LLM |
| Incident Memory | Correlates changed files against past production incidents via Azure AI Search | ✅ Implemented (`agents/history_agent` + `mcp_servers/azure_mcp_server`) |
| Verification Readiness | Detects missing/deleted tests for changed files; triggers Copilot to write them | ✅ Implemented (`agents/coverage_agent`) |
| Release Context | Scores deploy timing risk: day-of-week, time-of-day, holiday proximity, release proximity | ✅ Implemented (`agents/timing_agent`), fully deterministic, no external calls |
| Fixed-template GitHub publisher | Posts the verdict as a PR comment using a fixed markdown template; installs a fixed-template Actions workflow | ✅ Implemented (`agents/orchestrator/server.py`, `platform/server/services/github_service.py`) |
| Setup Platform | Guided GitHub + Azure onboarding, workflow installation | ✅ Implemented (`platform/`) |
| Incident ingestion pipeline | Keeps Incident Memory's index fresh from Azure Monitor alerts and logs | ✅ Implemented (`function_deploy/`, `mcp_servers/azure_mcp_server/ingest.py`) |
| Optional Foundry governance | Tracing, content-safety check on generated text, policy guardrails, quality evaluation | ✅ Implemented, fully optional (`foundry/deployment_config`) |
| Security Preflight (untrusted-input boundary) | Zero-cost, deterministic scan for secrets/unsafe workflows/injection-shaped text, run before evidence modules | 🆕 To be built in v2 (see `04_System_Design.md` §7) |
| Human override | Maintainer can override a blocked verdict; reason recorded for audit | 🆕 Partially present (manual GitHub merge override); formal override endpoint to be added |

## 9. Evidence Modules (detail)

| Module | New name | Old name | Weight | Signal |
|---|---|---|---|---|
| 1 | **Change Intelligence** | Diff Analyst | 30% | Dangerous diff patterns: secrets, removed error handling, removed retries/backoff, risky schema/migration changes |
| 2 | **Incident Memory** | History Agent | 25% | Semantic + strict-match correlation of changed files against past production incidents |
| 3 | **Verification Readiness** | Coverage Agent | 25% | Missing or deleted tests for changed Python files; auto-nudges Copilot to fill gaps |
| 4 | **Release Context** | Timing Agent | 20% | Deploy-window risk: weekday/weekend, time-of-day, US federal holidays, release-date proximity |

Each module returns a standardized `AgentResult` (`agent_name`, `risk_score_modifier` 0–100, `status` pass/warning/critical, `findings[]`, `recommended_action`). The Deterministic Verdict & Policy Layer combines them: `score = 100 − Σ(modifier × weight)`, clamped 0–100; any `critical` status or score below 70 forces a `blocked` decision.

## 10. GitHub Workflow

- **Trigger:** PR `opened`, `synchronize`, or `reopened`.
- **Installation:** a single, fixed-content GitHub Actions YAML file, committed by the Setup Platform via the GitHub Contents API — no manual YAML editing required.
- **Execution:** the workflow (via `actions/github-script`) fetches the diff and changed files itself and calls the orchestrator's `/analyze` endpoint — or, in the current dogfooding setup, the FastAPI webhook receiver (`/webhook/pr`) reacts directly to the GitHub webhook with HMAC signature verification.
- **Publishing:** the verdict is posted as a PR review comment using a fixed markdown template (score, status table, collapsible risk brief, collapsible rollback playbook). A failing verdict fails the GitHub Actions job, which shows as a blocked check on the PR.
- **Test-gap nudge:** a second, separate fixed-template comment addressed to `@copilot` is posted when coverage gaps are found, with de-duplication so it isn't posted twice.

## 11. Security and Trust Requirements

- PR titles, bodies, comments, branch names, and diff text are **untrusted input** — they must never be interpreted as instructions to any agent or to SafeLane itself (see Security Preflight, `04_System_Design.md` §7).
- No LLM output may directly control GitHub permissions, merges, deployments, or shell commands. All GitHub-facing actions go through the Fixed-template GitHub publisher.
- The final score and block/greenlight decision are computed by deterministic code (`agents/verdict_agent`), never by an LLM. LLM calls, where used, only reword the human-readable brief/playbook and are always optional.
- Secrets (GitHub PATs, Azure keys) are encrypted at rest with Fernet (AES) and never logged or echoed back to the client (`platform/server/services/auth_service.py`).
- Webhook payloads are verified with an HMAC-SHA256 signature check before any processing (`agents/orchestrator/server.py::_verify_signature`).
- A human with GitHub write access can always override a blocked verdict by merging manually; SafeLane does not have merge authority itself.
- **Known gaps to close in v2** (see `04_System_Design.md` §12 for full list): a hardcoded fallback JWT secret, disabled TLS certificate verification on the Postgres connection, and no formal untrusted-input/prompt-injection screen yet. These are flagged, not hidden.

## 12. Expected Outputs

- A GitHub PR comment containing: Deployment Confidence Score, GREENLIGHT/BLOCKED tag, a per-module status table, a full markdown risk brief, and (if blocked) a rollback playbook with concrete `git revert` steps.
- A failing GitHub Actions check when blocked, so the PR shows as not mergeable-by-default.
- A `POST /analyze` JSON response (`VerdictReport`) usable for the hackathon demo, VS Code sidebar (optional), or any future dashboard.
- Structured logs / OpenTelemetry spans per agent call when Foundry tracing is connected.

## 13. Success Criteria

- SafeLane produces a correct, explainable verdict on at least three prepared demo PRs: one clearly safe, one clearly risky (secret / removed retry), and one borderline (missing tests only).
- End-to-end latency from PR event to posted comment is under ~60 seconds in the demo environment.
- The system degrades gracefully (no crash, no silent wrong answer) when Azure OpenAI, Azure AI Search, or Foundry are unreachable.
- A first-time non-expert user can install SafeLane into a fresh repo using the Setup Platform in under 10 minutes.
- Judges can articulate, after a two-minute demo, what makes SafeLane different from "just another CI check."

## 14. Demo Requirements

- A seed/demo repository with a few prepared PRs (safe, risky, borderline) ready in advance — do not rely on live improvisation only.
- At least one **offline-safe fallback**: if Azure OpenAI/Foundry is unreachable at demo time, Change Intelligence and the Verdict brief must still produce a correct, if less richly worded, result from heuristics/templates alone.
- A short, rehearsed narration script mapping each of the four modules to one line of the sample PR's risk brief.
- Screenshots or a short recording as a backup in case live network access fails during the presentation.

## 15. Hackathon Constraints

- Limited time: prioritize the renaming/documentation pass and the Security Preflight addition over large new features.
- Limited budget: default to the free tiers of Azure OpenAI/Azure AI Search/Foundry (or skip them and run on heuristics/templates only).
- Unreliable model availability: every LLM-touching code path already has a deterministic fallback — preserve this property in any new code.
- Avoid unnecessary infrastructure: reuse the existing FastAPI services, SQLite/Postgres split, and Azure Functions ingestion rather than introducing new infrastructure for the hackathon.
- Keep setup simple enough for a beginner to follow using `07_Beginner_Vibe_Coding_Guide.md`.

## 16. Free or Low-Cost Technology Assumptions

- **Required, free:** Python 3.12, FastAPI, Pydantic, SQLite (dev), pytest, GitHub Actions (free minutes on public/small repos), GitHub REST API.
- **Optional, has a free tier:** Azure OpenAI (GPT-4o-mini), Azure AI Search (Free/Basic tier), Azure Content Safety, Application Insights, Microsoft Foundry project tracing — all behind environment-variable checks that fall back to deterministic behavior when absent.
- **Optional, may need a paid tier at scale only:** Azure PostgreSQL, Azure Container Apps, Azure Functions (Consumption plan has a generous free grant). Not required for a local/dev demo, which can run entirely on SQLite + `uvicorn --reload`.
- See `05_Requirements.md` for the full, labeled dependency list.

## 17. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Azure OpenAI/Foundry unavailable during demo | Every LLM call path already falls back to heuristics/templates; verify this fallback explicitly before the demo (see `07_Beginner_Vibe_Coding_Guide.md` stage 14). |
| Renaming introduces bugs by breaking imports | Rename in documentation/comments first; only rename Python identifiers with test coverage in place, one module at a time (see `08_Code_Integration_Map.md`). |
| Hardcoded fallback URLs/secrets leak into a public demo repo | Move all hardcoded fallback URLs and the JWT default secret into required environment variables before any public demo (tracked in `04_System_Design.md` §12). |
| A judge asks "can the AI do something dangerous?" | Be ready to point at the Fixed-template GitHub publisher and the deterministic Verdict layer as the answer: the model never has GitHub write authority or command execution ability. |
| Rate limits / freemium cap hit mid-demo | The orchestrator's in-memory `USAGE_TRACKER` defaults to 500 free analyses; confirm `PRISM_FREE_TIER_LIMIT` is set generously (or `0` to disable) for the demo instance. |
| Time runs out before Security Preflight is built | It's additive and independent of the rest of the pipeline — safe to demo v2 without it and add it as a "what's next" slide. |

## 18. Future Improvements

- Formal Security Preflight module with a fixture-based backtest suite (already scoped in `04_System_Design.md` §7).
- A human-override API endpoint with audit logging, rather than relying only on manual GitHub merge override.
- A persisted, shared-store version of the freemium usage tracker (Redis/Postgres) for multi-instance deployments.
- Expanding Incident Memory beyond Azure AI Search to an optional free/local vector store for users without Azure access.
- Re-evaluating the VS Code extension and dashboard as a post-hackathon roadmap item.
