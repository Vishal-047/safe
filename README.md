# SafeLane v2

*An AI-powered pre-deployment risk gate for GitHub pull requests.*

> "Tests pass" is not the same thing as "safe to ship." SafeLane reads every pull request the way a careful senior engineer would, and gives it a **Deployment Confidence Score (0–100)** with a plain-English explanation — posted right on the PR.

This README is written for a beginner. If a term is unfamiliar, keep reading — it's explained the first time it comes up.

---

## What SafeLane Is

SafeLane watches your GitHub pull requests. When one is opened or updated, four independent "Evidence Modules" each look at the change from a different angle, and a final layer combines their findings into one score and a clear explanation. That explanation is posted as a comment directly on the pull request — no dashboard required to see it.

## What Problem It Solves

A normal CI pipeline only asks: *"did the tests pass?"* It never asks whether the file you just touched has broken production before, whether your new code paths actually have test coverage, or whether it's a smart idea to deploy right before a long weekend. SafeLane asks those questions automatically, every time.

## How the Change Assurance Fabric Works

"Change Assurance Fabric" is the name for SafeLane's whole decision-making pipeline. Here's the plain-English version of what happens, in order, every time a PR is opened or updated:

1. GitHub tells SafeLane a PR event happened.
2. SafeLane fetches the diff (the actual code changes) and the list of changed files.
3. Four Evidence Modules look at the change **at the same time** (not one after another — this is why it's fast).
4. A scoring layer combines their four opinions into one number, 0 to 100.
5. SafeLane posts a comment on the PR with the score and the reasoning — using a **fixed template**, meaning the AI never gets to freely decide what GitHub action to take. It can only explain; a separate, predictable piece of code does the actual posting.

## What Each Evidence Module Does

| Module | In plain English |
|---|---|
| **Change Intelligence** | Reads the actual code diff looking for danger signs: secret keys accidentally committed, error-handling code that got deleted, retry/timeout logic that got removed, or risky database changes. |
| **Incident Memory** | Checks whether the files you're changing have caused real production problems before, by searching past incident records. |
| **Verification Readiness** | Checks whether your changed code actually has tests. If not, it can automatically ask GitHub Copilot to write them. |
| **Release Context** | Checks *when* you're deploying — Friday afternoon and holiday-eve deploys score riskier than a Tuesday morning deploy, purely from the calendar, no AI needed for this one. |

## What the Fixed-template GitHub publisher Does

This is the one piece of SafeLane that's allowed to actually write to GitHub — post a comment, fail a check. It's called "fixed-template" on purpose: it fills in a pre-written template with the score and findings, rather than letting an AI model freely decide what text (or what action) to send to GitHub. This is a safety design choice — it means SafeLane's AI components can only ever *explain*, never *act*, on GitHub.

## How the Existing Code Contributes

SafeLane v2 is not a rewrite. Most of the hard work is already built and working — it just used older internal names. This table shows what each old piece became:

| Old name (in the code) | New name (in this documentation) |
|---|---|
| Diff Analyst | Change Intelligence |
| History Agent | Incident Memory |
| Coverage Agent | Verification Readiness |
| Timing Agent | Release Context |
| Verdict Agent | Deterministic Verdict & Policy Layer |
| Orchestrator | Change Assurance Fabric Controller |

You do not need to rename every file in the codebase to benefit from this — the mapping above is enough to read the code with the new mental model. See `08_Code_Integration_Map.md` for exactly which files, if any, are worth renaming.

## Project Structure

```
SafeLane/
├── agents/
│   ├── orchestrator/       # Fabric Controller — receives PR events, runs everything
│   ├── diff_analyst/       # Change Intelligence
│   ├── history_agent/      # Incident Memory
│   ├── coverage_agent/     # Verification Readiness
│   ├── timing_agent/       # Release Context
│   ├── verdict_agent/      # Scoring + risk brief + rollback playbook
│   └── shared/              # The shared data shapes every module agrees on
├── platform/                # The setup wizard — connects GitHub + Azure, installs SafeLane into a repo
│   ├── server/               # Backend for the setup wizard
│   └── frontend/             # The setup wizard's web page
├── mcp_servers/
│   └── azure_mcp_server/     # Talks to Azure AI Search for Incident Memory
├── foundry/
│   └── deployment_config/    # Optional cloud tracing/safety features + cloud deployment scripts
├── function_deploy/          # Optional background job that keeps Incident Memory's data fresh
├── tests/                    # Automated tests — unit/ (fast, no internet) and integration/ (fuller checks)
├── vscode_extension/         # Optional IDE sidebar — not required for the core product
├── SafeLane Docs/             # You are here — all the planning documents
├── requirements.txt          # Python packages to install
└── .env.example              # Template for your configuration/secrets file
```

## How to Install the Project

You'll need **Python 3.12** installed on your computer. If you're not sure whether you have it, open a terminal and run:

```bash
python3 --version
```

If that shows `Python 3.12.x` (or newer), you're set. If not, install Python from [python.org](https://www.python.org/downloads/) first.

Then, from inside the project folder:

```bash
# Install the main dependencies
pip install -r requirements.txt --break-system-packages

# Install the setup platform's dependencies too
pip install -r platform/requirements.txt --break-system-packages
```

*(`--break-system-packages` may not be needed on your machine — if `pip install` works without it, that's fine too. It's only there for certain Linux setups that otherwise refuse the install.)*

## How to Configure Environment Variables

SafeLane reads its configuration from a file called `.env`. A template already exists at `.env.example` — copy it:

```bash
cp .env.example .env
```

Now open `.env` in any text editor. **You do not need to fill in every line.** Here's what's actually required to run SafeLane locally with no cloud services at all:

- Nothing! SafeLane's core pipeline (all four Evidence Modules) works with an *empty* `.env` file, using heuristics and calendar logic only.

Here's what unlocks extra features, and is safe to skip for now:

| Variable | What it unlocks if you fill it in |
|---|---|
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | Richer AI-written explanations (Change Intelligence + risk brief wording) |
| `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_KEY` | Real Incident Memory — correlating files with past production incidents |
| `AZURE_FOUNDRY_PROJECT_CONNECTION_STRING`, `APPLICATIONINSIGHTS_CONNECTION_STRING` | Cloud tracing/dashboards for every agent call |
| `GITHUB_WEBHOOK_SECRET` | Verifies that webhook events really came from GitHub (**recommended** once you're not just testing locally) |
| `JWT_SECRET`, `ENCRYPTION_KEY` | Required before you connect a real GitHub account through the Setup Platform — see the warning below |

**Security note:** `JWT_SECRET` and `ENCRYPTION_KEY` currently have insecure defaults if left blank in some parts of the code. Always set real values for these two before connecting a real GitHub token — see `04_System_Design.md` §12.1 for the exact fix. For a quick, throwaway local test, you can generate a Fernet key like this:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste the output as `ENCRYPTION_KEY=` in your `.env`. For `JWT_SECRET`, any long random string works locally, e.g.:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## How to Run the Project Locally

You'll run two small web servers, each in its own terminal window.

**Terminal 1 — the Fabric Controller** (the brain that analyzes PRs):
```bash
uvicorn agents.orchestrator.server:app --reload --port 8000
```
Visit `http://localhost:8000/health` in your browser — you should see `{"status": "ok", "service": "prism"}`.

**Terminal 2 — the Setup Platform** (the wizard that connects GitHub):
```bash
cd platform
uvicorn server.app:app --reload --port 8080
```
Visit `http://localhost:8080` — you should see the setup wizard's web page.

## How to Run Tests

```bash
pytest -m unit          # fast tests, no internet needed — run these constantly
pytest -m integration    # fuller tests — Azure calls are stubbed, no real cloud account needed
pytest                    # everything (anything needing live cloud credentials skips itself automatically)
```

If a test fails, read the error message from the bottom up — the last few lines usually say exactly what went wrong.

## How to Connect GitHub

1. With the Setup Platform running (`http://localhost:8080`), open it in your browser.
2. Create a GitHub **Personal Access Token (PAT)** — a password-like string GitHub gives you so other tools can act on your behalf. On GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**, and grant it read/write access to the one repository you want to protect.
3. Paste that token into the Setup Platform when asked.
4. Choose the repository. SafeLane will commit a small workflow file (`.github/workflows/prism-gate.yml`) into that repo automatically — you don't write any YAML yourself.
5. Open (or update) a pull request in that repo. Within about a minute, you should see SafeLane's comment appear.

## How to Use Microsoft Foundry (If Available)

If you have `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, and `AZURE_FOUNDRY_PROJECT_CONNECTION_STRING` filled in your `.env`, SafeLane automatically starts using them — there's no separate switch to flip. You'll get richer AI-written findings and, if `APPLICATIONINSIGHTS_CONNECTION_STRING` is also set, a live trace of every agent call in the Azure Foundry dashboard.

## What to Use If Microsoft Foundry Is Unavailable

Nothing extra to do — just leave those variables blank. Every part of SafeLane that would use Foundry checks for the configuration first and quietly falls back to a deterministic version (heuristic scanning, template-based writing, standard log messages instead of cloud traces). This is intentional: **the pipeline was designed from the start to work with zero paid services**, since student/free-tier cloud access can be unreliable.

## How to Prepare the Hackathon Demo

1. Pick or create one repository you're allowed to modify freely.
2. Connect it through the Setup Platform (see above) a day or two *before* the demo, not right before — so you have time to fix anything that goes wrong.
3. Prepare **three PRs in advance**:
   - One clean, obviously-safe change.
   - One with an obvious problem (e.g., delete a `try/except` block, or remove a retry loop).
   - One that's just missing a test for a new function.
4. Run each one once beforehand and confirm SafeLane's comment looks right.
5. Rehearse mapping each line of the comment back to one of the four Evidence Modules — that's the story that makes the demo land.
6. Take a screenshot or short screen recording of each result as a backup, in case live internet/demo Wi-Fi is unreliable.

## Common Beginner Mistakes

- **Forgetting to start both servers.** The Fabric Controller (`:8000`) and the Setup Platform (`:8080`) are two separate processes — both need to be running.
- **Leaving `.env` unfilled and expecting Incident Memory to show real history.** With no Azure Search configured, it correctly says "no deployment connection" — that's not a bug, that's the safe fallback.
- **Using a GitHub token without the right permissions.** If workflow installation fails, double-check the token has write access to the *specific* repository you selected.
- **Testing on a repository with no commits yet.** SafeLane can bootstrap an empty repo, but it's simpler to test on a repo that already has at least one commit.
- **Not setting `ENCRYPTION_KEY`/`JWT_SECRET` before connecting a real token.** See the security note above — do this first, it takes one minute.
- **Panicking when a test fails.** Read `04_System_Design.md` §12.1 and `07_Beginner_Vibe_Coding_Guide.md` — most failures are one missing environment variable, not a broken feature.

## What to Do Next After Setup

1. Read `07_Beginner_Vibe_Coding_Guide.md` and follow it stage by stage if you haven't already.
2. Hand `01_Master_Prompt.md` to your coding agent when you're ready to start building/renaming.
3. Try SafeLane on a real PR with an intentional mistake, and confirm the score makes sense.
4. When you're comfortable, look at `04_System_Design.md` §7 for the next real feature to add: the Security Preflight module.
