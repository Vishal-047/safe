import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Annotated
from server.routers.auth import get_current_user
from server.services.github_service import commit_workflow_file

router = APIRouter()

SAFELANE_ORCHESTRATOR_URL = os.environ.get("SAFELANE_ORCHESTRATOR_URL")

class InstallRequest(BaseModel):
    owner: str
    repo: str

@router.get("/repos")
async def list_repos(current_user: Annotated[dict, Depends(get_current_user)]):
    pat = current_user.get("pat")
    if not pat:
        raise HTTPException(status_code=401, detail="No PAT in session")
        
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/repos?per_page=100&sort=updated",
            headers={
                "Authorization": f"Bearer {pat}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch repositories")
            
        repos = response.json()
        return [{"name": r["name"], "full_name": r["full_name"], "owner": r["owner"]["login"]} for r in repos]

@router.post("/install")
async def install_workflow(req: InstallRequest, current_user: Annotated[dict, Depends(get_current_user)]):
    if not SAFELANE_ORCHESTRATOR_URL:
        raise HTTPException(status_code=500, detail="SAFELANE_ORCHESTRATOR_URL environment variable is required")
        
    pat = current_user.get("pat")
    if not pat:
        raise HTTPException(status_code=401, detail="No PAT in session")
        
    try:
        await commit_workflow_file(req.owner, req.repo, pat, SAFELANE_ORCHESTRATOR_URL)
        return {"status": "success", "message": f"Workflow installed in {req.owner}/{req.repo}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
