# SafeLane v2 Code Integration Map

This folder replaces the previous single large integration document. Read only the file needed for the current implementation task.

## Reading order

1. Read [01 — Architecture and Migration](01-Architecture-and-Migration.md) before changing any code.
2. Use [02 — Repository Integration Map](02-Repository-Integration-Map.md) to find the correct source file, target responsibility, risk, and tests.
3. Read the relevant module file before refactoring that capability.
4. Read [11 — Tests and Completion](11-Tests-and-Completion.md) before marking a task complete.

## Files

| File | Load it when you need to… |
|---|---|
| [01 — Architecture and Migration](01-Architecture-and-Migration.md) | Understand the v2 design and safe order of work. |
| [02 — Repository Integration Map](02-Repository-Integration-Map.md) | Decide whether existing code is reused, renamed, wrapped, refactored, or replaced. |
| [03 — Contracts and Security](03-Contracts-and-Security.md) | Add typed v2 results, trust boundaries, or Security Preflight. |
| [04 — Change Intelligence](04-Change-Intelligence.md) | Refactor the current Diff Analyst. |
| [05 — Incident Memory](05-Incident-Memory.md) | Refactor the History Agent and Azure incident search. |
| [06 — Verification Readiness](06-Verification-Readiness.md) | Refactor the Coverage Agent. |
| [07 — Release Context](07-Release-Context.md) | Refactor the Timing Agent. |
| [08 — Fabric Controller and Verdict](08-Fabric-Controller-and-Verdict.md) | Implement parallel execution, fallback, scores, and policy gates. |
| [09 — GitHub Ingress and Publisher](09-GitHub-Ingress-and-Publisher.md) | Change webhook handling, PR output, and GitHub workflow integration. |
| [10 — Platform, Foundry, and Ingestion](10-Platform-Foundry-and-Ingestion.md) | Work on setup, optional Foundry, Azure Search, or Azure Functions. |
| [11 — Tests and Completion](11-Tests-and-Completion.md) | Add tests, validate a task, or decide whether legacy code can be removed. |

## Global rules

- Preserve working GitHub, Azure, and test behaviour while names move to v2.
- Treat all pull-request text and diff content as untrusted data.
- The model is optional; deterministic logic makes final decisions.
- Do not delete legacy code until its v2 replacement is tested.
- The four evidence modules have equal product standing: Change Intelligence, Incident Memory, Verification Readiness, and Release Context.
