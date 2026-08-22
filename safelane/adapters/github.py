import os
import hmac
import hashlib
import logging
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from safelane.contracts import PRPayload, RepoContext, VerdictReport
from safelane.fabric.controller import orchestrate
from safelane.fabric.publisher import publish_verdict

logger = logging.getLogger('safelane.server')

app = FastAPI(title="SafeLane Change Assurance Fabric")

def get_repo_context(repo: str) -> Optional[RepoContext]:
    # Mock lookup for MVP
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    return RepoContext(
        registration_id="mock-reg-id",
        owner=repo.split('/')[0] if '/' in repo else "unknown",
        repo=repo.split('/')[1] if '/' in repo else repo,
        gh_token=token
    )

@app.get("/health")
async def health():
    return {"status": "ok", "service": "safelane"}

async def _run_analysis(payload: PRPayload, repo_context: RepoContext):
    try:
        report = await orchestrate(payload, repo_context)
        await publish_verdict(report, payload.repo, payload.pr_number, repo_context.gh_token)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")

@app.post("/webhook/pr")
async def webhook_pr(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None)
):
    body = await request.body()
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    
    if secret:
        if not x_hub_signature_256:
            raise HTTPException(status_code=401, detail="Missing signature")
            
        expected_mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        expected_sig = f"sha256={expected_mac}"
        if not hmac.compare_digest(x_hub_signature_256, expected_sig):
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning("GITHUB_WEBHOOK_SECRET is not set, bypassing verification. Set it for production use.")

    data = await request.json()
    
    event = request.headers.get("x-github-event")
    if event != "pull_request":
        return {"status": "ignored", "reason": "not a pull_request event"}
        
    action = data.get("action")
    if action not in ["opened", "synchronize", "reopened"]:
        return {"status": "ignored", "reason": f"action {action} ignored"}
        
    pr_data = data.get("pull_request", {})
    repo_data = data.get("repository", {})
    
    repo_name = repo_data.get("full_name")
    if not repo_name:
        raise HTTPException(status_code=400, detail="Missing repository full_name")

    repo_context = get_repo_context(repo_name)
    if not repo_context:
        raise HTTPException(status_code=404, detail="Repo context not found")

    # Fetch real PR diff and changed files from GitHub API
    diff_text = ""
    changed_files = []
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {repo_context.gh_token}", "User-Agent": "SafeLane"}
            diff_resp = await client.get(
                f"https://api.github.com/repos/{repo_name}/pulls/{pr_data.get('number', 0)}",
                headers={**headers, "Accept": "application/vnd.github.v3.diff"}
            )
            if diff_resp.status_code == 200:
                diff_text = diff_resp.text
                
            files_resp = await client.get(
                f"https://api.github.com/repos/{repo_name}/pulls/{pr_data.get('number', 0)}/files",
                headers={**headers, "Accept": "application/vnd.github.v3+json"}
            )
            if files_resp.status_code == 200:
                changed_files = [f["filename"] for f in files_resp.json()]
    except Exception as e:
        logger.error(f"Failed to fetch PR details from GitHub: {e}")

    payload = PRPayload(
        pr_number=pr_data.get("number", 0),
        repo=repo_name,
        changed_files=changed_files,
        diff=diff_text,
        timestamp=pr_data.get("updated_at", "1970-01-01T00:00:00Z"),
        head_sha=pr_data.get("head", {}).get("sha", ""),
        skip_autofix=False
    )
    
    background_tasks.add_task(_run_analysis, payload, repo_context)
    return {"status": "accepted"}

@app.post("/analyze")
async def analyze(payload: PRPayload):
    # Synchronous endpoint
    repo_context = get_repo_context(payload.repo)
    report = await orchestrate(payload, repo_context)
    return report
