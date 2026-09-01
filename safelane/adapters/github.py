import os
import hmac
import hashlib
import logging
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from safelane.contracts import PRPayload, RepoContext, VerdictReport
from safelane.fabric.controller import orchestrate
from safelane.fabric.publisher import publish_verdict

logger = logging.getLogger('safelane.server')

app = FastAPI(title="SafeLane Change Assurance Fabric")

async def get_repo_context(repo: str) -> Optional[RepoContext]:
    # 1. Primary path: look up repo registration from shared DB (OAuth token)
    try:
        import sys
        # Add platform directory to path so orchestrator can access shared DB service
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        platform_path = os.path.join(project_root, "platform")
        if platform_path not in sys.path:
            sys.path.insert(0, platform_path)

        from server.services.db import get_registration
        from server.services.auth_service import decrypt_pat
        parts = repo.split('/')
        if len(parts) == 2:
            owner, repo_name = parts[0], parts[1]
            reg = await get_registration(owner, repo_name)
            if reg and reg.is_active:
                gh_token = decrypt_pat(reg.encrypted_pat)
                logger.info(f"Using OAuth token from DB for {repo}")
                return RepoContext(
                    registration_id=str(reg.id),
                    owner=owner,
                    repo=repo_name,
                    gh_token=gh_token
                )
    except Exception as e:
        logger.warning(f"DB lookup failed for {repo}: {e}")

    # 2. Fallback: use GITHUB_TOKEN env var if DB lookup failed or repo not registered
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        logger.warning(f"Falling back to GITHUB_TOKEN for {repo}")
        return RepoContext(
            registration_id="fallback-token",
            owner=repo.split('/')[0] if '/' in repo else "unknown",
            repo=repo.split('/')[1] if '/' in repo else repo,
            gh_token=token
        )

    return None

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
    
    # Only verify signature when both the secret is configured AND a signature is provided
    # GitHub Actions curl does not send X-Hub-Signature-256 headers
    if secret and x_hub_signature_256:
        expected_mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        expected_sig = f"sha256={expected_mac}"
        if not hmac.compare_digest(x_hub_signature_256, expected_sig):
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif secret and not x_hub_signature_256:
        logger.warning("GITHUB_WEBHOOK_SECRET is set but no signature was provided. Proceeding without verification (GitHub Actions mode).")

    import json
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
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

    repo_context = await get_repo_context(repo_name)
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
    repo_context = await get_repo_context(payload.repo)
    report = await orchestrate(payload, repo_context)
    return report
